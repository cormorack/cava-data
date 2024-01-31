"""CAVA_DATA_STACK Configs."""

from typing import Dict, List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class StackSettings(BaseSettings):
    """Application settings"""

    name: str = "cava-data"
    stage: str = "production"

    owner: Optional[str] = None
    client: Optional[str] = None
    owner: Optional[str] = None
    project: str = "CAVA"

    vpc: Optional[str] = None
    security_group: Optional[str] = None
    user_role: Optional[str] = None

    # Stack environment
    region: str = "us-west-2"
    account_id: str = "123556123145"
    # services_elb: str
    domain_name: Optional[str] = None
    certificate_arn: Optional[str] = None

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
    max_concurrent: Optional[int] = None

    model_config = SettingsConfigDict(env_prefix="CAVA_DATA_STACK_", env_file=".env")

