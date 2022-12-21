# Cava data AWS Lambda Deployment

The Lambda stack is also deployed by the [AWS CDK](https://aws.amazon.com/cdk/) utility. Under the hood, CDK will create the deployment package required for AWS Lambda, upload it to AWS, and handle the creation of the Lambda and API Gateway resources.

1. Install CDK and connect to your AWS account. This step is only necessary once per AWS account.

    ```bash
    # install cdk dependencies
    cd resources/aws
    pip install -r requirements.txt
    npm install

    npm run cdk bootstrap # Deploys the CDK toolkit stack into an AWS environment
    ```

2. Pre-Generate CFN template

    ```bash
    npm run cdk synth  # Synthesizes and prints the CloudFormation template for this stack
    ```

3. Update settings in a `.env` file.

    ```env
    CAVA_DATA_STACK_NAME="cava-data"
    CAVA_DATA_STACK_STAGE="dev"
    CAVA_DATA_STACK_MEMORY=3008
    ```

    Available settings for cava data app:

    ```python
    CAVA_DATA_STACK_USER_ROLE
    CAVA_DATA_STACK_VPC
    CAVA_DATA_STACK_SECURITY_GROUP
    CAVA_DATA_STACK_ACCOUNT_ID
    CAVA_DATA_STACK_SERVICES_ELB
    CAVA_DATA_STACK_DOMAIN_NAME
    CAVA_DATA_STACK_CERTIFICATE_ARN
    CAVA_DATA_STACK_ENV
    ```

4. Deploy

    ```bash
    npm run cdk deploy # Deploys the stack(s) cava-services-production in cdk/app.py
    ```
