"""CAVA_DATA_STACK Configs."""
from typing import Dict, Optional

import pydantic


class StackSettings(pydantic.BaseSettings):
    """Application settings"""

    class Config:
        """model config"""

        env_file = ".env"
        env_prefix = "CAVA_DATA_STACK_"

    name: str = "cava-data"
    stage: str = "production"

    owner: Optional[str]
    project: str = "CAVA"

    vpc: Optional[str]
    security_group: Optional[str]
    user_role: Optional[str]

    # Stack environment
    region: str = "us-west-2"
    account_id: str = "123556123145"
    services_elb: str
    domain_name: Optional[str]
    certificate_arn: Optional[str]

    # Default options for cava-data service
    env: Dict = {
        "DATA_QUEUE": "data-queue",
        "OOI_USERNAME": "XXXXXXXX",
        "OOI_TOKEN": "XXXXXXXXXXX",
        "REDIS_URI": "redis://localhost",
        "RABBITMQ_URI": "amqp://guest@localhost:5672//",
        "GOOGLE_SERVICE_JSON": "mybucket/service-json.json"
    }
    is_sqs: bool = False


    ###########################################################################
    # AWS LAMBDA
    # The following settings only apply to AWS Lambda deployment
    # more about lambda config: https://www.sentiatechblog.com/aws-re-invent-2020-day-3-optimizing-lambda-cost-with-multi-threading
    timeout: int = 10
    memory: int = 1536

    # The maximum of concurrent executions you want to reserve for the function.
    # Default: - No specific limit - account limit.
    max_concurrent: Optional[int]

    @pydantic.root_validator
    def set_sqs(cls, values):
        env_values = values.get('env')
        rabbitmq_uri = env_values.get('RABBITMQ_URI')
        if not isinstance(rabbitmq_uri, str):
            raise TypeError("RABBITMQ_URI must be a string!")
        
        if rabbitmq_uri.startswith('sqs://'):
            env_values.update({
                'REGION': values.get('region'),
            })
            values.update({
                'env': env_values,
                'is_sqs': True
            })
            return values
        return values
