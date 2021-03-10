# cava-data

Cabled Array Data Access Interface

## Development

To run locally, use `docker-compose`.

1. Build development image. Run the command below on the root of the repository.

    ```bash
    docker-compose -f resources/docker/docker-compose.yaml build
    ```

2. Run the development image.

    ```bash
    # Set AWS Credentials that have access to ooi-data bucket.
    export AWS_ACCESS_KEY_ID=XXXXXXXXXXXXXXXXXXXXX
    export AWS_SECRET_ACCESS_KEY=XXXXXXXXXXXXXXXXX
    export GOOGLE_SERVICE_JSON=bucket/path/to/google-creds.json
    docker-compose -f resources/docker/docker-compose.yaml up
    ```
