from typing import Any
import boto3
from botocore.exceptions import ClientError
import os

def get_parameter(parameter_name: str) -> Any:
    ssm_client = boto3.client('ssm', region_name=os.getenv("AWS_REGION"))
    try:
        response = ssm_client.get_parameter(Name=parameter_name, WithDecryption=True)
        return response['Parameter']['Value']
    except ClientError as e:
        raise Exception(f"Error fetching parameter {parameter_name}: {str(e)}")

def get_api_key() -> str:
    return get_parameter(os.getenv("SSM_PARAMETER_PATH") + "api-key")

def get_target_credentials() -> dict:
    prefix = os.getenv("SSM_PARAMETER_PATH")
    if not prefix:
        raise Exception("SSM_PARAMETER_PATH environment variable is not set.")
    return {
        'username': get_parameter(prefix + "username"),
        'password': get_parameter(prefix + "password")
    }
