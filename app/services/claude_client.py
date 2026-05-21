import json
import time
import boto3
from botocore.config import Config as BotoConfig
from flask import current_app


class BedrockClient:
    """Talks to AWS Bedrock for AI analysis (Claude or Nova depending on env)."""

    # Model configs
    MODELS = {
        'production': {
            'model_id': 'us.anthropic.claude-3-5-haiku-20241022-v1:0',
            'provider': 'anthropic',
            # Claude 3.5 Haiku pricing (per 1K tokens)
            'input_cost_per_1k': 0.001,
            'output_cost_per_1k': 0.005,
        },
        'testing': {
            'model_id': 'us.amazon.nova-lite-v1:0',
            'provider': 'amazon',
            # Nova Lite pricing (per 1K tokens)
            'input_cost_per_1k': 0.0006,
            'output_cost_per_1k': 0.0024,
        },
    }

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            region = current_app.config.get('AWS_REGION', 'us-east-2')
            access_key = current_app.config.get('AWS_ACCESS_KEY_ID')
            secret_key = current_app.config.get('AWS_SECRET_ACCESS_KEY')

            if not access_key or not secret_key:
                raise ValueError(
                    "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY must be set in .env. "
                    "Get them from IAM → Users → Security Credentials → Create Access Key."
                )

            # 90s read timeout prevents hanging forever on slow/stuck connections
            boto_cfg = BotoConfig(
                read_timeout=90,
                connect_timeout=10,
                retries={'max_attempts': 1},
            )
            self._client = boto3.client(
                'bedrock-runtime',
                region_name=region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                config=boto_cfg,
            )
        return self._client

    def _get_model_config(self):
        """Get model config based on APP_ENV."""
        env = current_app.config.get('APP_ENV', 'testing').lower()
        if env not in self.MODELS:
            print(f"[bedrock] Unknown APP_ENV '{env}', defaulting to 'testing'")
            env = 'testing'
        return self.MODELS[env], env

    def analyze(self, system_prompt, user_message, max_tokens=4096, temperature=0.2):
        """Send a prompt to Bedrock, return parsed response + token/cost info.

        temperature: 0.0-1.0. Lower = more deterministic. Default 0.2 for
        consistent structured output. Use 0.4-0.5 for creative writing.
        """
        try:
            model_cfg, env_name = self._get_model_config()
            model_id = model_cfg['model_id']
            provider = model_cfg['provider']

            print(f"[bedrock] Using {model_id} (env={env_name}, max_tokens={max_tokens})")
            t0 = time.time()

            # Build request body based on provider
            if provider == 'anthropic':
                body = self._build_anthropic_body(system_prompt, user_message, max_tokens, temperature)
            else:
                body = self._build_amazon_body(system_prompt, user_message, max_tokens, temperature)

            # Invoke the model
            response = self.client.invoke_model(
                modelId=model_id,
                contentType='application/json',
                accept='application/json',
                body=json.dumps(body),
            )

            # Parse response
            response_body = json.loads(response['body'].read())
            elapsed = time.time() - t0
            print(f"[bedrock] API call completed in {elapsed:.1f}s")

            if provider == 'anthropic':
                return self._parse_anthropic_response(response_body, model_cfg)
            else:
                return self._parse_amazon_response(response_body, model_cfg)

        except Exception as e:
            print(f"[bedrock] Error: {e}")
            return {
                'error': str(e),
                'response': None,
                'tokens_used': 0,
                'cost_usd': 0,
            }

    def _build_anthropic_body(self, system_prompt, user_message, max_tokens, temperature):
        """Build request body for Anthropic Claude models on Bedrock."""
        return {
            'anthropic_version': 'bedrock-2023-05-31',
            'max_tokens': max_tokens,
            'temperature': temperature,
            'system': system_prompt,
            'messages': [
                {
                    'role': 'user',
                    'content': user_message,
                }
            ],
        }

    def _build_amazon_body(self, system_prompt, user_message, max_tokens, temperature):
        """Build request body for Amazon Nova models on Bedrock."""
        # Nova has a strict maxTokens limit of 10240 (5120 is safer for output)
        safe_max_tokens = min(max_tokens, 5120)
        return {
            'inferenceConfig': {
                'max_new_tokens': safe_max_tokens,
                'temperature': temperature,
            },
            'system': [
                {'text': system_prompt}
            ],
            'messages': [
                {
                    'role': 'user',
                    'content': [
                        {'text': user_message}
                    ],
                }
            ],
        }

    def _parse_anthropic_response(self, response_body, model_cfg):
        """Parse Claude response from Bedrock."""
        raw_text = response_body.get('content', [{}])[0].get('text', '')

        # Token usage
        usage = response_body.get('usage', {})
        input_tokens = usage.get('input_tokens', 0)
        output_tokens = usage.get('output_tokens', 0)

        # Cost calculation
        cost = (
            (input_tokens / 1000) * model_cfg['input_cost_per_1k'] +
            (output_tokens / 1000) * model_cfg['output_cost_per_1k']
        )

        # Try to parse as JSON
        parsed = self._try_parse_json(raw_text)

        return {
            'response': parsed,
            'raw_text': raw_text,
            'tokens_used': input_tokens + output_tokens,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'cost_usd': round(cost, 6),
        }

    def _parse_amazon_response(self, response_body, model_cfg):
        """Parse Amazon Nova response from Bedrock."""
        output = response_body.get('output', {})
        message = output.get('message', {})
        content_list = message.get('content', [])
        raw_text = content_list[0].get('text', '') if content_list else ''

        # Token usage
        usage = response_body.get('usage', {})
        input_tokens = usage.get('inputTokens', 0)
        output_tokens = usage.get('outputTokens', 0)

        # Cost calculation
        cost = (
            (input_tokens / 1000) * model_cfg['input_cost_per_1k'] +
            (output_tokens / 1000) * model_cfg['output_cost_per_1k']
        )

        # Try to parse as JSON
        parsed = self._try_parse_json(raw_text)

        return {
            'response': parsed,
            'raw_text': raw_text,
            'tokens_used': input_tokens + output_tokens,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'cost_usd': round(cost, 6),
        }

    def _try_parse_json(self, raw_text):
        """Try to parse raw text as JSON, stripping code fences if present."""
        try:
            cleaned = raw_text.strip()
            if cleaned.startswith('```json'):
                cleaned = cleaned[7:]
            elif cleaned.startswith('```'):
                cleaned = cleaned[3:]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]
            return json.loads(cleaned.strip())
        except (json.JSONDecodeError, ValueError):
            return raw_text


# Singleton instance — Amazon Bedrock (Claude 3.5 Haiku / Nova Lite)
claude = BedrockClient()
