import json
import boto3
from flask import current_app


class BedrockClient:
    """Talks to AWS Bedrock for AI analysis (Claude or Nova depending on env)."""

    # Model configs
    # APP_ENV values: 'productionHigh' | 'productionLow' | 'testing'
    MODELS = {
        'productionHigh': {
            'model_id': 'us.anthropic.claude-sonnet-4-5-20250929-v1:0',
            'provider': 'anthropic',
            # Claude Sonnet 4.6 pricing (per 1K tokens)
            'input_cost_per_1k': 0.003,
            'output_cost_per_1k': 0.015,
        },
        'productionLow': {
            'model_id': 'us.anthropic.claude-haiku-4-5-20251001-v1:0',
            'provider': 'anthropic',
            # Claude Haiku 4.5 pricing (per 1K tokens)
            'input_cost_per_1k': 0.001,
            'output_cost_per_1k': 0.005,
        },
        'testing': {
            'model_id': 'us.amazon.nova-lite-v1:0',
            'provider': 'amazon',
            # Amazon Nova Lite pricing (per 1K tokens)
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

            self._client = boto3.client(
                'bedrock-runtime',
                region_name=region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
            )
        return self._client

    def _get_model_config(self):
        """Get model config based on APP_ENV.
        Valid values: 'productionHigh', 'productionLow', 'testing'
        """
        env = current_app.config.get('APP_ENV', 'testing')  # preserve camelCase — do NOT lowercase
        if env not in self.MODELS:
            print(f"[bedrock] Unknown APP_ENV '{env}', defaulting to 'testing'. Valid: {list(self.MODELS.keys())}")
            env = 'testing'
        return self.MODELS[env], env

    def analyze(self, system_prompt, user_message, max_tokens=4096, temperature=0.2, force_json=False, model_override=None):
        """Send a prompt to Bedrock, return parsed response + token/cost info.

        temperature: 0.0-1.0. Lower = more deterministic. Default 0.2 for
        consistent structured output. Use 0.4-0.5 for creative writing.
        force_json: If True, prefill the assistant response with '{' to force
        JSON output (Anthropic models only). Prevents the model from asking
        clarifying questions instead of producing structured output.
        model_override: If set (e.g., 'productionHigh'), forces a specific model
        regardless of APP_ENV. Use for tasks that need stronger reasoning.
        """
        try:
            if model_override and model_override in self.MODELS:
                model_cfg = self.MODELS[model_override]
                env_name = model_override
                print(f"[bedrock] Using model override: {model_override} ({model_cfg['model_id']})")
            else:
                model_cfg, env_name = self._get_model_config()
            model_id = model_cfg['model_id']
            provider = model_cfg['provider']

            print(f"[bedrock] Using {model_id} (env={env_name})")

            # Build request body based on provider
            if provider == 'anthropic':
                body = self._build_anthropic_body(system_prompt, user_message, max_tokens, temperature, force_json)
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

            if provider == 'anthropic':
                return self._parse_anthropic_response(response_body, model_cfg, force_json)
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

    def _build_anthropic_body(self, system_prompt, user_message, max_tokens, temperature, force_json=False):
        """Build request body for Anthropic Claude models on Bedrock."""
        messages = [
            {
                'role': 'user',
                'content': user_message,
            }
        ]

        # Prefill technique: start the assistant's response with '{' to force JSON
        # This prevents the model from asking clarifying questions or outputting text
        if force_json:
            messages.append({
                'role': 'assistant',
                'content': '{',
            })

        return {
            'anthropic_version': 'bedrock-2023-05-31',
            'max_tokens': max_tokens,
            'temperature': temperature,
            'system': system_prompt,
            'messages': messages,
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

    def _parse_anthropic_response(self, response_body, model_cfg, force_json=False):
        """Parse Claude response from Bedrock."""
        raw_text = response_body.get('content', [{}])[0].get('text', '')

        # When force_json is enabled, the assistant prefill was '{' so the
        # model's continuation won't include the opening brace — prepend it.
        if force_json and raw_text and not raw_text.strip().startswith('{'):
            raw_text = '{' + raw_text

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

    def _fix_json_newlines(self, text):
        """Escape literal newlines inside JSON string values.

        LLMs sometimes output JSON with raw newlines inside string values
        (e.g. multi-line cover letter text), which is invalid JSON.
        This walks character-by-character and escapes them.
        """
        result = []
        in_string = False
        escape_next = False

        for char in text:
            if escape_next:
                result.append(char)
                escape_next = False
                continue
            if char == '\\':
                result.append(char)
                escape_next = True
                continue
            if char == '"':
                in_string = not in_string
                result.append(char)
                continue
            if in_string and char == '\n':
                result.append('\\n')
                continue
            if in_string and char == '\r':
                result.append('\\r')
                continue
            result.append(char)

        return ''.join(result)

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
            cleaned = cleaned.strip()

            # First try direct parse
            try:
                return json.loads(cleaned)
            except (json.JSONDecodeError, ValueError):
                pass

            # If that fails, fix literal newlines inside JSON string values and retry
            fixed = self._fix_json_newlines(cleaned)
            return json.loads(fixed)
        except (json.JSONDecodeError, ValueError):
            return raw_text


# Singleton instance — Amazon Bedrock (Claude 3.5 Haiku / Nova Lite)
claude = BedrockClient()


class NvidiaClient:
    """Talks to NVIDIA NIM API for AI analysis (Llama-3.3-Nemotron for generation,
    Nemotron-3-embed for embeddings/RAG)."""

    NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

    MODELS = {
        'generation': {
            'model_id': 'nvidia/llama-3.3-nemotron-super-49b-v1',
            'api_key_name': 'NVIDIA_NEMOTRON_API_KEY',
            'default_api_key': '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',
            'provider': 'nvidia',
            # Approximate pricing (per 1K tokens)
            'input_cost_per_1k': 0.0,
            'output_cost_per_1k': 0.0,
        },
        'embedding': {
            'model_id': 'nvidia/nv-embedqa-e5-v5',
            'api_key_name': 'NVIDIA_EMBED_API_KEY',
            'default_api_key': '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',
            'provider': 'nvidia',
        },
    }

    def __init__(self):
        self._session = None

    @property
    def session(self):
        """Lazy-init a requests session for connection pooling."""
        if self._session is None:
            import requests
            self._session = requests.Session()
        return self._session

    def _get_api_key(self, model_type='generation'):
        """Get API key for the specified model type."""
        model_cfg = self.MODELS[model_type]
        # Try env/config first, fall back to hardcoded default
        try:
            key = current_app.config.get(model_cfg['api_key_name'])
        except RuntimeError:
            key = None
        if not key:
            key = model_cfg['default_api_key']
        return key

    def analyze(self, system_prompt, user_message, max_tokens=4096, temperature=0.2,
                force_json=False, model_override=None):
        """Send a prompt to NVIDIA NIM API, return parsed response + token/cost info.

        Uses the same interface as BedrockClient.analyze() for drop-in compatibility.
        """
        try:
            model_cfg = self.MODELS['generation']
            model_id = model_cfg['model_id']
            api_key = self._get_api_key('generation')

            print(f"[nvidia] Using {model_id}")

            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            }

            # Build messages (OpenAI-compatible format)
            messages = [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_message},
            ]

            # Prefill technique for JSON forcing
            if force_json:
                messages.append({'role': 'assistant', 'content': '{'})

            body = {
                'model': model_id,
                'messages': messages,
                'max_tokens': max_tokens,
                'temperature': temperature,
                'stream': False,
            }

            response = self.session.post(
                f"{self.NVIDIA_BASE_URL}/chat/completions",
                headers=headers,
                json=body,
                timeout=120,
            )

            if response.status_code != 200:
                error_text = response.text[:500]
                print(f"[nvidia] HTTP {response.status_code}: {error_text}")
                return {
                    'error': f"HTTP {response.status_code}: {error_text}",
                    'response': None,
                    'tokens_used': 0,
                    'cost_usd': 0,
                }

            data = response.json()
            return self._parse_response(data, model_cfg, force_json)

        except Exception as e:
            print(f"[nvidia] Error: {e}")
            return {
                'error': str(e),
                'response': None,
                'tokens_used': 0,
                'cost_usd': 0,
            }

    def embed(self, texts, input_type='query'):
        """Generate embeddings using NVIDIA Nemotron embedding model.

        Args:
            texts: A single string or list of strings to embed.
            input_type: 'query' for search queries, 'passage' for documents to be searched.

        Returns:
            dict with 'embeddings' (list of float vectors), 'tokens_used', 'error' (if any).
        """
        try:
            if isinstance(texts, str):
                texts = [texts]

            model_cfg = self.MODELS['embedding']
            model_id = model_cfg['model_id']
            api_key = self._get_api_key('embedding')

            print(f"[nvidia-embed] Using {model_id} for {len(texts)} text(s)")

            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            }

            body = {
                'model': model_id,
                'input': texts,
                'input_type': input_type,
                'encoding_format': 'float',
                'truncate': 'END',
            }

            response = self.session.post(
                f"{self.NVIDIA_BASE_URL}/embeddings",
                headers=headers,
                json=body,
                timeout=30,
            )

            if response.status_code != 200:
                error_text = response.text[:500]
                print(f"[nvidia-embed] HTTP {response.status_code}: {error_text}")
                return {
                    'error': f"HTTP {response.status_code}: {error_text}",
                    'embeddings': None,
                    'tokens_used': 0,
                }

            data = response.json()
            embeddings = [item['embedding'] for item in data.get('data', [])]
            usage = data.get('usage', {})
            total_tokens = usage.get('total_tokens', 0)

            print(f"[nvidia-embed] Generated {len(embeddings)} embedding(s), {total_tokens} tokens")

            return {
                'embeddings': embeddings,
                'tokens_used': total_tokens,
                'model': model_id,
            }

        except Exception as e:
            print(f"[nvidia-embed] Error: {e}")
            return {
                'error': str(e),
                'embeddings': None,
                'tokens_used': 0,
            }

    def _parse_response(self, data, model_cfg, force_json=False):
        """Parse NVIDIA NIM API response (OpenAI-compatible format)."""
        choices = data.get('choices', [])
        if not choices:
            return {
                'error': 'No choices in response',
                'response': None,
                'tokens_used': 0,
                'cost_usd': 0,
            }

        raw_text = choices[0].get('message', {}).get('content', '')

        # When force_json is enabled, the assistant prefill was '{' so
        # prepend it if the model's continuation doesn't start with '{'
        if force_json and raw_text and not raw_text.strip().startswith('{'):
            raw_text = '{' + raw_text

        # Token usage
        usage = data.get('usage', {})
        input_tokens = usage.get('prompt_tokens', 0)
        output_tokens = usage.get('completion_tokens', 0)

        # Cost calculation
        cost = (
            (input_tokens / 1000) * model_cfg.get('input_cost_per_1k', 0) +
            (output_tokens / 1000) * model_cfg.get('output_cost_per_1k', 0)
        )

        # Try to parse as JSON (reuse BedrockClient's helper via composition)
        parsed = self._try_parse_json(raw_text)

        return {
            'response': parsed,
            'raw_text': raw_text,
            'tokens_used': input_tokens + output_tokens,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'cost_usd': round(cost, 6),
        }

    def _fix_json_newlines(self, text):
        """Escape literal newlines inside JSON string values."""
        result = []
        in_string = False
        escape_next = False

        for char in text:
            if escape_next:
                result.append(char)
                escape_next = False
                continue
            if char == '\\':
                result.append(char)
                escape_next = True
                continue
            if char == '"':
                in_string = not in_string
                result.append(char)
                continue
            if in_string and char == '\n':
                result.append('\\n')
                continue
            if in_string and char == '\r':
                result.append('\\r')
                continue
            result.append(char)

        return ''.join(result)

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
            cleaned = cleaned.strip()

            try:
                return json.loads(cleaned)
            except (json.JSONDecodeError, ValueError):
                pass

            fixed = self._fix_json_newlines(cleaned)
            return json.loads(fixed)
        except (json.JSONDecodeError, ValueError):
            return raw_text


# Singleton instance — NVIDIA NIM (Llama-3.3-Nemotron + Nemotron-3-embed)
nvidia = NvidiaClient()
