import os 
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
JWT_SECRET = os.getenv("jwt_secret")  
algorithm = os.getenv("algorithm")
JWT_ALGORITHM = os.getenv("jwt_algorithm", algorithm)
TEST_DATABASE_URL=os.getenv("TEST_DATABASE_URL")
