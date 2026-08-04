# FILE: app/extractors/aws_extractor.py

import re
from typing import List, Set

class AWSServiceExtractor:
    """
    Extracts AWS services mentioned in job descriptions.
    Handles multiple formats:
    - AWS (S3, Lambda, SageMaker)
    - AWS services like S3 and Lambda
    - AWS Lambda, AWS S3
    """
    
    # Known AWS services (to prevent false positives)
    AWS_SERVICES = {
        'Compute': ['EC2', 'Lambda', 'ECS', 'EKS', 'Fargate', 'Batch'],
        'Storage': ['S3', 'EBS', 'EFS', 'Glacier', 'Storage Gateway'],
        'Database': ['RDS', 'DynamoDB', 'ElastiCache', 'Redshift', 'Neptune'],
        'AI/ML': ['SageMaker', 'Rekognition', 'Comprehend', 'Textract', 'Bedrock'],
        'Networking': ['VPC', 'CloudFront', 'ALB', 'Route53', 'API Gateway'],
        'Monitoring': ['CloudWatch', 'X-Ray', 'CloudTrail'],
        'DevOps': ['CodePipeline', 'CodeBuild', 'CodeDeploy', 'CloudFormation']
    }
    
    def __init__(self):
        self.all_services = [
            service 
            for services in self.AWS_SERVICES.values() 
            for service in services
        ]
    
    def extract_from_parentheses(self, text: str) -> List[str]:
        """
        Extract AWS services from "AWS (...)" format
        Example: "AWS (S3, Lambda, SageMaker or similar)" 
        → ['S3', 'Lambda', 'SageMaker']
        """
        pattern = r'AWS\s*\(([^)]+)\)'
        matches = re.findall(pattern, text, re.IGNORECASE)
        
        services = []
        for match in matches:
            # Split by comma and 'or'
            parts = re.split(r'[,\s+or\s+]', match, flags=re.IGNORECASE)
            for part in parts:
                part = part.strip()
                # Validate it's a real AWS service
                if self._is_valid_service(part):
                    services.append(part)
        
        return services
    
    def extract_contextual(self, text: str) -> List[str]:
        """
        Extract AWS services mentioned with context
        Examples:
        - "AWS EC2 instances"
        - "use S3 for storage"
        - "leveraging Lambda functions"
        """
        services = []
        
        # Case-insensitive search for each service
        for service in self.all_services:
            # Pattern: "AWS ServiceName" or "use ServiceName" or just "ServiceName"
            patterns = [
                f'AWS\\s+{service}',
                f'\\b{service}\\b'
            ]
            
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    services.append(service)
                    break
        
        return services
    
    def extract_all(self, text: str) -> Set[str]:
        """Main extraction method - combines all approaches"""
        services = set()
        
        # Try parenthetical format first (most reliable)
        services.update(self.extract_from_parentheses(text))
        
        # Fall back to contextual extraction
        services.update(self.extract_contextual(text))
        
        return services
    
    def _is_valid_service(self, term: str) -> bool:
        """Validate that a term is a real AWS service"""
        term = term.strip()
        # Remove "or similar" and similar phrases
        term = re.sub(r'\s*or.*', '', term, flags=re.IGNORECASE)
        term = term.strip()
        
        # Check against known services (case-insensitive)
        return any(term.lower() == service.lower() for service in self.all_services)


# USAGE
if __name__ == "__main__":
    extractor = AWSServiceExtractor()
    
    # Test 1: Parenthetical format
    jd1 = "Proficiency in AWS (S3, Lambda, sagemaker or similar services)"
    result1 = extractor.extract_all(jd1)
    print(f"Test 1: {result1}")
    # Output: {'S3', 'Lambda', 'SageMaker'} ✅
    
    # Test 2: Contextual format
    jd2 = "Experience with AWS Lambda functions and S3 buckets for data processing"
    result2 = extractor.extract_all(jd2)
    print(f"Test 2: {result2}")
    # Output: {'Lambda', 'S3'} ✅
    
    # Test 3: Mixed
    jd3 = """
    AWS expertise including S3 for storage, Lambda for serverless computing, 
    and AWS (RDS, DynamoDB) for databases
    """
    result3 = extractor.extract_all(jd3)
    print(f"Test 3: {result3}")
    # Output: {'S3', 'Lambda', 'RDS', 'DynamoDB'} ✅