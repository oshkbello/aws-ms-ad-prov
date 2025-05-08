import boto3
import botocore.exceptions
import re
import time

def lambda_handler(event, context):
    business_id = event["businessId"]
    account_id = event["awsAccountId"]
    stack_name = f"ad-stack-{business_id}"
    REGION = "ca-central-1"
    BUCKET_NAME = "cf-templates-1gxf2an4sweo5-ca-central-1"
    TEMPLATE_FILE = "microsoft-ad-template.yml"

    # Validate BusinessId format
    if not re.match(r"^[a-zA-Z0-9-]+$", business_id):
        raise Exception(f"❌ BusinessId '{business_id}' contains invalid characters. Allowed: letters, numbers, hyphens.")

    # Assume into business account
    sts = boto3.client('sts')
    creds = sts.assume_role(
        RoleArn=f"arn:aws:iam::{account_id}:role/PlatformSupportRole",
        RoleSessionName="CreateADStackSession"
    )["Credentials"]

    cf = boto3.client("cloudformation", region_name=REGION,
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"]
    )
    s3 = boto3.client("s3", region_name=REGION)
    sm = boto3.client("secretsmanager", region_name=REGION,
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"]
    )
    ec2 = boto3.client("ec2", region_name=REGION,
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"]
    )

    # Validate secret exists
    secret_name = f"cloud-desktop/biz-{business_id}/directoryAdminPassword"
    try:
        sm.get_secret_value(SecretId=secret_name)
        print(f"✅ Secret {secret_name} found.")
    except sm.exceptions.ResourceNotFoundException:
        raise Exception(f"❌ Secret {secret_name} not found — aborting.")

    # Validate VPC and subnets
    vpc_id = event["VpcId"]
    subnet_a = event["DirectorySubnetA"]
    subnet_b = event["DirectorySubnetB"]

    try:
        # Retry loop to wait for DNS settings to be applied
        max_retries = 5
        retry_delay = 3  # seconds

        for attempt in range(max_retries):
            dns_support = ec2.describe_vpc_attribute(VpcId=vpc_id, Attribute='enableDnsSupport')["EnableDnsSupport"]["Value"]
            dns_hostnames = ec2.describe_vpc_attribute(VpcId=vpc_id, Attribute='enableDnsHostnames')["EnableDnsHostnames"]["Value"]

            if dns_support and dns_hostnames:
                print(f"✅ VPC {vpc_id} has DNS support and hostnames enabled.")
                break

            if attempt < max_retries - 1:
                print(f"⏳ Waiting for VPC DNS settings... attempt {attempt + 1}/{max_retries}")
                time.sleep(retry_delay)
        else:
            raise Exception(f"❌ VPC {vpc_id} does not have DNS support or hostnames enabled after {max_retries} retries.")

        # Validate subnets exist
        ec2.describe_subnets(SubnetIds=[subnet_a, subnet_b])
        print(f"✅ VPC {vpc_id} and subnets {subnet_a}, {subnet_b} validated.")
    except botocore.exceptions.ClientError as e:
        raise Exception(f"❌ Failed to validate VPC/subnets: {str(e)}")

    # Generate signed URL for CloudFormation template
    signed_url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET_NAME, "Key": TEMPLATE_FILE},
        ExpiresIn=600
    )

    # Prepare CloudFormation parameters
    parameters = [
        {"ParameterKey": "BusinessId", "ParameterValue": business_id},
        {"ParameterKey": "VpcId", "ParameterValue": vpc_id},
        {"ParameterKey": "DirectorySubnetA", "ParameterValue": subnet_a},
        {"ParameterKey": "DirectorySubnetB", "ParameterValue": subnet_b}
    ]

    # Launch CloudFormation stack
    try:
        cf.create_stack(
            StackName=stack_name,
            TemplateURL=signed_url,
            Parameters=parameters,
            Capabilities=["CAPABILITY_NAMED_IAM"]
        )
        print(f"✅ Stack {stack_name} creation initiated.")
    except cf.exceptions.AlreadyExistsException:
        print(f"⚠️ Stack {stack_name} already exists. Skipping create_stack.")
    except botocore.exceptions.ClientError as e:
        raise Exception(f"❌ CloudFormation create_stack error: {str(e)}")

    return {
        "status": "stack-launched",
        "stackName": stack_name,
        "businessId": business_id,
        "awsAccountId": account_id
    }
