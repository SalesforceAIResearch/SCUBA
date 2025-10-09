import dotenv
import os
from scuba.helpers.salesforce_commands import authorize_using_access_token

dotenv.load_dotenv(override=True)

org_alias = os.getenv("ORG_ALIAS")
assert org_alias is not None, "ORG_ALIAS is not set in the .env file."
authorize_using_access_token(org_alias)