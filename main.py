import argparse
import boto3
from docker import DockerClient
import time

def create_cloudwatch_client(aws_access_key_id, aws_secret_access_key, aws_region):
    return boto3.client(
        'logs',
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=aws_region
    )

def ensure_cloudwatch_log_group_exists(client, log_group_name):
    try:
        client.create_log_group(logGroupName=log_group_name)
    except client.exceptions.ResourceAlreadyExistsException:
        pass  # Log group already exists, no action needed

def ensure_cloudwatch_log_stream_exists(client, log_group_name, log_stream_name):
    try:
        client.create_log_stream(logGroupName=log_group_name, logStreamName=log_stream_name)
    except client.exceptions.ResourceAlreadyExistsException:
        pass  # Log stream already exists, no action needed

def run_docker_container(docker_image, bash_command):
    client = DockerClient.from_env()
    container = client.containers.run(docker_image, command=['bash', '-c', bash_command], detach=True)
    return container

def monitor_container_logs(container, cloudwatch_client, log_group_name, log_stream_name):
    next_token = None
    for line in container.logs(stream=True):
        event = {
            'timestamp': int(time.time() * 1000),
            'message': line.decode('utf-8')
        }
        if next_token:
            response = cloudwatch_client.put_log_events(
                logGroupName=log_group_name,
                logStreamName=log_stream_name,
                logEvents=[event],
                sequenceToken=next_token
            )
        else:
            response = cloudwatch_client.put_log_events(
                logGroupName=log_group_name,
                logStreamName=log_stream_name,
                logEvents=[event]
            )
        next_token = response.get('nextSequenceToken')

def main():
    parser = argparse.ArgumentParser(description="Run a Docker container and stream logs to AWS CloudWatch.")
    parser.add_argument("--docker-image", required=True, help="Name of the Docker image")
    parser.add_argument("--bash-command", required=True, help="Bash command to run inside the Docker image")
    parser.add_argument("--aws-cloudwatch-group", required=True, help="Name of the AWS CloudWatch group")
    parser.add_argument("--aws-cloudwatch-stream", required=True, help="Name of the AWS CloudWatch stream")
    parser.add_argument("--aws-access-key-id", required=True, help="AWS Access Key ID")
    parser.add_argument("--aws-secret-access-key", required=True, help="AWS Secret Access Key")
    parser.add_argument("--aws-region", required=True, help="AWS Region")

    args = parser.parse_args()

    cloudwatch_client = create_cloudwatch_client(args.aws_access_key_id, args.aws_secret_access_key, args.aws_region)
    ensure_cloudwatch_log_group_exists(cloudwatch_client, args.aws_cloudwatch_group)
    ensure_cloudwatch_log_stream_exists(cloudwatch_client, args.aws_cloudwatch_group, args.aws_cloudwatch_stream)

    container = run_docker_container(args.docker_image, args.bash_command)
    try:
        monitor_container_logs(container, cloudwatch_client, args.aws_cloudwatch_group, args.aws_cloudwatch_stream)
    finally:
        container.stop()

if __name__ == "__main__":
    main()
