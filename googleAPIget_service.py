import argparse
import httplib2

from googleapiclient.discovery import build
from oauth2client import file
from oauth2client import tools
from oauth2client import client


def get_service(api_name, api_version, scope, client_secrets_path, usernameToken = ""):
  """Get a service that communicates to a Google API.

  Args:
    api_name: string The name of the api to connect to.
    api_version: string The api version to connect to.
    scope: A list of strings representing the auth scopes to authorize for the
      connection.
    client_secrets_path: string A path to a valid client secrets file.

  Returns:
    A service that is connected to the specified API.
  """
  # Parse command-line arguments.
  parser = argparse.ArgumentParser(
      formatter_class=argparse.RawDescriptionHelpFormatter,
      parents=[tools.argparser])
  flags = parser.parse_args([])

  if usernameToken == "":
    combined_client_secrets_path = client_secrets_path
  else:
    combined_client_secrets_path = usernameToken+"-"+client_secrets_path

  # Set up a Flow object to be used if we need to authenticate.
  flow = client.flow_from_clientsecrets(
      combined_client_secrets_path, scope=scope,
      message=tools.message_if_missing(combined_client_secrets_path))

  # Prepare credentials, and authorize HTTP object with them.
  # If the credentials don't exist or are invalid run through the native client
  # flow. The Storage object will ensure that if successful the good
  # credentials will get written back to a file.

  if usernameToken == "":
    combined_data_file_name = api_name + '.dat'
  else:
    combined_data_file_name = usernameToken+"-"+api_name + '.dat'

  storage = file.Storage(combined_data_file_name)
  credentials = storage.get()
  if credentials is None or credentials.invalid:
    credentials = tools.run_flow(flow, storage, flags)
  http = credentials.authorize(http=httplib2.Http())

  # Build the service object.
  service = build(api_name, api_version, http=http)

  return service