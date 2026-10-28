import os 
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
JWT_SECRET = os.getenv("jwt_secret")  
algorithm = os.getenv("algorithm")
JWT_ALGORITHM = os.getenv("jwt_algorithm", algorithm)
TEST_DATABASE_URL=os.getenv("TEST_DATABASE_URL")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME") 
S3_REGION_NAME = os.getenv("S3_REGION_NAME")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID") 
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY") 
AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION")
