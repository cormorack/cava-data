"""Construct App."""

import os
from typing import Any, Dict, List, Optional

from aws_cdk import App, CfnOutput, Duration, Environment, Stack, Tag
from aws_cdk import aws_apigatewayv2_alpha as apigw
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda
from aws_cdk import aws_logs as logs
from aws_cdk.aws_apigatewayv2_integrations_alpha import HttpLambdaIntegration
from config import StackSettings
from constructs import Construct

settings = StackSettings()


class cavaDataLambdaStack(Stack):
    """
    Titiler Lambda Stack

    This code is freely adapted from
    - https://developmentseed.org/titiler/deployment/aws/lambda/ @developmentseed
    - https://github.com/developmentseed/titiler/tree/main/deployment (Using the aws example)
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        memory: int = 1024,
        timeout: int = 30,
        concurrent: Optional[int] = None,
        permissions: Optional[List[iam.PolicyStatement]] = None,
        environment: Optional[Dict] = None,
        code_dir: str = "./",
        vpc: Optional[str] = None,
        security_group: Optional[str] = None,
        user_role: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Define stack."""
        super().__init__(scope, id, **kwargs)

        permissions = permissions or []
        environment = environment or {}
        # Get IVpc
        security_groups = None
        if vpc is not None: 
            vpc = ec2.Vpc.from_lookup(self, f"{id}-vpc", vpc_id=vpc)
            if security_group is not None:
                sg = ec2.SecurityGroup.from_lookup_by_id(self, f"{id}-sg", security_group_id=security_group)
                security_groups = [sg]
        lambda_function = aws_lambda.DockerImageFunction(
            self,
            f"{id}-lambda",
            code=aws_lambda.DockerImageCode.from_image_asset(
                directory=os.path.abspath(code_dir),
                file="lambda/Dockerfile",
            ),
            memory_size=memory,
            reserved_concurrent_executions=concurrent,
            timeout=Duration.seconds(timeout),
            environment=environment,
            log_retention=logs.RetentionDays.ONE_WEEK,
            vpc=vpc,
            security_groups=security_groups
        )

        if user_role is not None:
            iuser = iam.User.from_user_name(self, f"{id}-user", user_name=user_role)
            lambda_function.add_permission(f"{id}-user-perm", principal=iam.ArnPrincipal(iuser.user_arn))

        for perm in permissions:
            lambda_function.add_to_role_policy(perm)

        api = apigw.HttpApi(
            self,
            f"{id}-endpoint",
            default_integration=HttpLambdaIntegration(
                f"{id}-integration", handler=lambda_function
            ),
        )
        CfnOutput(self, "Endpoint", value=api.url)

app = App()

perms = [
    iam.PolicyStatement(
        actions=['s3:*'],
        resources=[
            f"*"
        ]
    )
]
if settings.is_sqs is True:
    perms.append(
        iam.PolicyStatement(
            actions=['sqs:*'],
            resources=[
                f"*"
            ]
        )
    )

# Tag infrastructure
for key, value in {
    "Project": settings.name,
    "Environment": settings.stage,
    "Owner": settings.owner,
    "Project": settings.project,
}.items():
    if value:
        Tag(key, value)

stack_env = Environment(
    account=settings.account_id,
    region=settings.region
)
lambda_stack = cavaDataLambdaStack(
    app,
    f"{settings.name}-lambda-{settings.stage}",
    memory=settings.memory,
    timeout=settings.timeout,
    concurrent=settings.max_concurrent,
    permissions=perms,
    environment=settings.env,
)

app.synth()
