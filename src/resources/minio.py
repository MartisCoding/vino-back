from src.config import MinioConfig
from minio import Minio
from loguru import logger

def create_minio_client(config: MinioConfig) -> Minio:
    logger.debug("Creating MinIO client for endpoint {}:{}", config.host, config.port)
    client =  Minio(
        endpoint=f"{config.host}:{config.port}",
        access_key=config.access_key,
        secret_key=config.secret_key,
        secure=False
    )
    logger.info("MinIO client created for endpoint {}:{}", config.host, config.port)
    return client
    
    
    
    
    