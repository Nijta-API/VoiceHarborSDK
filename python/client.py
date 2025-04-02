#!/usr/bin/env python3
"""
Voice Harbor Client Module

This module provides a Python client for interacting with the Voice Harbor service.
It includes functionality to:
  - Create a job on the server.
  - Parse and upload supported audio and YAML files.
  - Poll for file availability and download results.
  - Execute the client as a command-line tool.

Supported file formats now include:
    .wav, .mp3, .flac, .ogg, .m4a, .yaml

Usage:
    python voice_harbor_client.py --base-url <BASE_URL> --token <AUTH_TOKEN> --inputs-dir <INPUT_DIRECTORY>
"""

import requests
import yaml
import mimetypes
import logging
import time  # For sleep delays
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import tqdm
import argparse
import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Define supported file formats (PDF removed).
SUPPORTED_FORMATS = {'.wav', '.mp3', '.flac', '.ogg', '.m4a', '.yaml'}
VERSION = "0.45.1"

class VoiceHarborClient:
    """
    A Python client for the Voice Harbor service.

    The client interacts with the Voice Harbor API to manage jobs, upload files, and download results.
    Files are uploaded using a server-provided signed URL, and the job is associated with a unique job_id.
    The server stores files using a target path of the form: {token}/{job_id}/{filename}.

    Attributes:
        base_url (str): The base URL of the Voice Harbor API.
        job_id (str): The job identifier provided by the server.
        id_token (str): Optional authorization token for API requests.
        session (requests.Session): A persistent session for HTTP requests.
        input_files (list): List of input files (Path objects) from the given directory.
    """

    def __init__(self, base_url: str, job_id: str, token: str = "", inputs_dir: str = "") -> None:
        """
        Initialize the VoiceHarborClient instance.

        Args:
            base_url (str): The base URL for the Voice Harbor API.
            job_id (str): The job identifier.
            token (str, optional): Authorization token for API access. Defaults to "".
            inputs_dir (str, optional): Directory path containing files to be uploaded. Defaults to "".
        """
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.id_token = token
        self.job_id = job_id
        self.input_files = self.parse_files(Path(inputs_dir))

    @classmethod
    def create_job(cls, base_url: str, token: str) -> str:
        """
        Create a new job by calling the /api/jobs endpoint.

        Args:
            base_url (str): The base URL for the Voice Harbor API.
            token (str): Authorization token for API access.

        Returns:
            str: The generated job_id.

        Raises:
            requests.HTTPError: If the HTTP request returned an unsuccessful status code.
        """
        endpoint = f"{base_url}/api/jobs"
        headers = {"Authorization": token} if token else {}
        response = requests.post(endpoint, headers=headers)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Created job with id: {data['job_id']}")
        return data["job_id"]
    
    @classmethod
    def get_jobs(cls, base_url: str, token: str) -> list:
        """
        Retrieve a list of jobs associated with the authenticated token.
    
        Returns:
            list: A list of job objects, each typically containing job details such as 'job_id', 'token', and 'created_at'.
        """
        endpoint = f"{base_url}/api/jobs"
        headers = {"Authorization": token} if token else {}
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Retrieved jobs: {data}")
        return data.get("jobs", [])

    @classmethod
    def get_job_content(cls, base_url: str, token: str, job_id: str) -> list:
        """
        Retrieve all job content items for the current job.
    
        Returns:
            list: A list of content items for the job. Each item typically includes fields such as 'id', 'job_id', 
                  'file_name', 'audio_duration', and 'created_at'.
        """
        endpoint = f"{base_url}/api/jobs/{job_id}/content"
        headers = {"Authorization": token} if token else {}
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Retrieved job content: {data}")
        return data.get("jobContent", [])

    @classmethod
    def create_developer_token(cls, base_url: str, admin_token: str) -> str:
        """
        Map an admin token to a new developer (usage) token and store it in a YAML file.

        Args:
            admin_token (str): The admin token to be mapped.
            base_url (str): The base URL of the Voice Harbor service.

        Returns:
            str: The file path to the stored YAML credential containing the developer token.
        """
        endpoint = f"{base_url}/api/admin/developer-token"
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.post(endpoint, headers=headers)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Received developer token: {data}")
        developer_token = data.get("developerToken", "")
        
        timestamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
        credentials_dir = Path("./credentials")
        credentials_dir.mkdir(parents=True, exist_ok=True)
        filename = f"VoiceHarbor_Developer.credential.{timestamp}.yaml"
        filepath = credentials_dir / filename
        logger.info(f"Received developer token stored below: {filepath}.")
        filepath.write_text(yaml.safe_dump({"developerToken": developer_token}))
        
        return str(filepath)

    @classmethod
    def get_developer_tokens(cls, base_url: str, admin_token: str) -> list:
        """
        Retrieve all developer tokens associated with the given admin token.
    
        Args:
            admin_token (str): The admin token to query.
    
        Returns:
            list: A list of dictionaries, each containing a developer token and its creation timestamp.
        """
        endpoint = f"{base_url}/api/admin/developer-tokens"
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Retrieved developer tokens: {data}")
        return data.get("developerTokens", [])
        
    def parse_files(self, inputs_dir: Path) -> list:
        """
        Parse and filter files in the specified input directory based on supported formats.

        Args:
            inputs_dir (Path): Path to the directory containing input files.

        Returns:
            list: A list of Path objects for files that match the supported formats.
        """
        files = [
            file_path for file_path in inputs_dir.iterdir()
            if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_FORMATS
        ]
        logger.info(f"Found {len(files)} files to upload.")
        return files

    def set_id_token(self, token: str) -> None:
        """
        Set or update the authorization token.

        Args:
            token (str): The new authorization token.
        """
        self.id_token = token

    def get_signed_url(self, file_name: str, file_type: str) -> str:
        """
        Request a signed URL from the server for uploading a file.

        The signed URL is used to securely upload a file using an HTTP PUT request.

        Args:
            file_name (str): The name of the file to be uploaded.
            file_type (str): The MIME type of the file.

        Returns:
            str: The signed URL for file upload.

        Raises:
            requests.HTTPError: If the HTTP request returned an unsuccessful status code.
        """
        endpoint = f"{self.base_url}/api/jobs/{self.job_id}/files/upload-url"
        headers = {"Authorization": self.id_token} if self.id_token else {}
        payload = {"fileName": file_name, "fileType": file_type}
        response = self.session.post(endpoint, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data["signedUrl"]

    def submit_file(self, file_path: Path) -> str:
        """
        Upload a single file using a signed URL.

        The server constructs the target storage path as {token}/{job_id}/{filename}.

        Args:
            file_path (Path): The path to the file that will be uploaded.

        Returns:
            str: The name of the file that was uploaded.

        Raises:
            requests.HTTPError: If any HTTP request fails.
        """
        file_path = Path(file_path)
        file_type, _ = mimetypes.guess_type(str(file_path))
        filename = file_path.name
        mime_type = file_type or "application/octet-stream"
        signed_url = self.get_signed_url(filename, mime_type)
        headers = {"Content-Type": mime_type}
        with file_path.open("rb") as f:
            resp = self.session.put(signed_url, data=f, headers=headers)
            resp.raise_for_status()
        return filename

    def submit_files(self, job_params: dict) -> dict:
        """
        Upload multiple input files concurrently.

        Each file in the input directory is uploaded in parallel. The method updates the
        job_params dictionary by appending the names of successfully uploaded files under the 'files' key.

        Args:
            job_params (dict): A dictionary containing job parameters, expected to have a key "files" which is a list.

        Returns:
            dict: The updated job_params dictionary with uploaded file names included.
        """
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_file = {executor.submit(self.submit_file, file): file for file in self.input_files}
            for future in tqdm.tqdm(as_completed(future_to_file), total=len(future_to_file), desc="Submitting files"):
                file_path = future_to_file[future]
                try:
                    target = future.result()
                    job_params['files'].append(target)
                    logger.info(f"Uploaded {file_path.name} as {target}")
                except Exception as e:
                    logger.error(f"Failed to upload {file_path.name}: {e}")
        return job_params

    def submit_job(self, job_parameters: dict) -> Path:
        """
        Create and upload a YAML job file containing the job parameters.

        The job file is saved locally with the filename "{job_id}.yaml" and then uploaded to the server.

        Args:
            job_parameters (dict): A dictionary containing the job parameters.

        Returns:
            Path: The local path to the YAML job file that was created and submitted.
        """
        job_file = Path(f"{self.job_id}.yaml")
        job_file.write_text(yaml.safe_dump(job_parameters, default_flow_style=False))
        self.submit_file(job_file)
        return job_file

    def get_signed_url_download(self, file_name: str) -> str:
        """
        Request a signed URL for downloading a file from the server.

        Args:
            file_name (str): The name of the file to be downloaded.

        Returns:
            str: The signed URL to download the file.

        Raises:
            requests.HTTPError: If the HTTP request returned an unsuccessful status code.
        """
        endpoint = f"{self.base_url}/api/jobs/{self.job_id}/files/download-url"
        headers = {"Authorization": self.id_token} if self.id_token else {}
        payload = {"fileName": file_name}
        response = self.session.post(endpoint, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Download signed URL response: {data}")
        return data["signedUrl"]

    def wait_for_file(self, file_name: str, timeout: int = 600, interval: int = 10) -> bool:
        """
        Poll the server to check if a file is available.

        This method repeatedly checks whether the specified file is finalized until the timeout
        is reached or the file is confirmed available.

        Args:
            file_name (str): The name of the file to check.
            timeout (int, optional): Maximum time in seconds to wait. Defaults to 600.
            interval (int, optional): Time in seconds between each poll. Defaults to 10.

        Returns:
            bool: True if the file is available before the timeout; otherwise, False.
        """
        finalized_endpoint = f"{self.base_url}/api/jobs/{self.job_id}/files/finalized"
        headers = {"Authorization": self.id_token} if self.id_token else {}
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                payload = {"fileName": file_name}
                response = self.session.post(finalized_endpoint, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                if data.get("exists", False):
                    logger.info(f"File {file_name} finalized (endpoint returned true).")
                    return True
                else:
                    logger.info(f"File {file_name} does not exist yet.")
            except Exception as e:
                logger.info(f"Error checking file existence for {file_name}: {e}")
            time.sleep(interval)
        logger.error(f"Timeout reached: {file_name} not available after {timeout} seconds.")
        return False

    def download_file(self, file_name: str, dest_dir: Path, timeout: int = 600, interval: int = 10) -> Path:
        """
        Wait for a file to become available and then download it.

        This method uses the signed URL for downloading the file and saves it to the specified destination directory.

        Args:
            file_name (str): The name of the file to download.
            dest_dir (Path): The destination directory where the file will be saved.
            timeout (int, optional): Maximum time in seconds to wait for the file. Defaults to 600.
            interval (int, optional): Polling interval in seconds. Defaults to 10.

        Returns:
            Path: The full local path to the downloaded file.

        Raises:
            Exception: If the file does not become available within the timeout period.
            requests.HTTPError: If the file download request fails.
        """
        if not self.wait_for_file(file_name, timeout, interval):
            raise Exception(f"File {file_name} not available after waiting {timeout} seconds.")
        signed_url = self.get_signed_url_download(file_name)
        response = self.session.get(signed_url)
        response.raise_for_status()
        dest_path = dest_dir / file_name
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with dest_path.open("wb") as f:
            f.write(response.content)
        logger.info(f"Downloaded {file_name} to {dest_path}")
        return dest_path

    def download_results(self, output_dir: str = "./results", timeout: int = 600, interval: int = 10, yaml: str = None) -> dict:
        """
        Download processed result files in parallel.

        If a YAML file is provided via the 'yaml' argument (which should contain a list of file names under the 'files' key),
        then those file names will be used. Otherwise, the instance's self.input_files are used.

        Args:
            output_dir (str, optional): Directory where the downloaded files will be stored. Defaults to "./results".
            timeout (int, optional): Maximum time in seconds to wait for each file. Defaults to 600.
            interval (int, optional): Polling interval in seconds for checking file availability. Defaults to 10.
            yaml (str, optional): Path to a YAML file containing a 'files' list. Defaults to None.

        Returns:
            dict: A dictionary mapping each original file name to a dict containing paths to the downloaded file and JSON.
        """
        output_dir_path = Path(output_dir)
        output_dir_path.mkdir(parents=True, exist_ok=True)
        downloaded = {}

        # Determine the list of file names based on the provided YAML file or instance input_files.
        if yaml is not None:
            job_yaml_file = Path(yaml)
            # Use a local alias for the YAML module to avoid conflict with the argument name.
            import yaml as yaml_module
            try:
                job_data = yaml_module.safe_load(job_yaml_file.read_text())
                file_names = job_data.get("files", [])
                logger.info(f"Loaded {len(file_names)} file names from YAML file {yaml}")
            except Exception as e:
                logger.error(f"Failed to load YAML file {yaml}: {e}")
                file_names = []
        else:
            file_names = [file.name for file in self.input_files]

        def download_pair(file_name: str) -> dict:
            base_name = Path(file_name).stem
            json_file_name = f"{base_name}.json"
            pair = {}
            try:
                # Download the main file.
                downloaded_file = self.download_file(file_name, output_dir_path, timeout, interval)
                # Download the corresponding JSON.
                downloaded_json = self.download_file(json_file_name, output_dir_path, timeout, interval)
                pair[file_name] = {
                    "file": str(downloaded_file),
                    "json": str(downloaded_json)
                }
            except Exception as e:
                logger.error(f"Failed to download results for {file_name}: {e}")
            return pair

        # Use ThreadPoolExecutor to download each file pair concurrently.
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(download_pair, file_name): file_name for file_name in file_names}
            for future in tqdm.tqdm(as_completed(futures), total=len(futures), desc="Downloading files"):
                result = future.result()
                downloaded.update(result)
        return downloaded


def main():
    """
    Entry point for the Voice Harbor Client CLI.

    This function parses command-line arguments, creates a new job on the server, uploads input files and
    the job file, and finally polls and downloads the processed results.
    """
    parser = argparse.ArgumentParser(description="Voice Harbor Client CLI")
    parser.add_argument("--base-url", type=str, required=True, help="Base URL for the Voice Harbor API")
    parser.add_argument("--token", type=str, required=True, help="Authorization token")
    parser.add_argument("--inputs-dir", type=str, required=True, help="Directory containing input files")
    parser.add_argument("--output-dir", type=str, default="./results", help="Directory to save the output files")
    parser.add_argument("--timeout", type=int, default=600, help="Timeout for waiting for files (in seconds)")
    parser.add_argument("--interval", type=int, default=10, help="Polling interval (in seconds)")
    parser.add_argument("--agents", nargs="+", default=["health-generic", "clinical"], help="List of agents to use")
    parser.add_argument("--prefix", type=str, default="", help="Optional prefix to include in the job parameters")
    
    args = parser.parse_args()
    
    # Create a new job on the server using the class method.
    job_id = VoiceHarborClient.create_job(args.base_url, args.token)
    logger.info(f"Job created on server with id: {job_id}")
    
    client = VoiceHarborClient(
        base_url=args.base_url,
        job_id=job_id,
        token=args.token,
        inputs_dir=args.inputs_dir
    )
    
    # Build job parameters. If a prefix is provided, include it.
    job_params = {"agents": args.agents, "files": []}
    if args.prefix:
        job_params["prefix"] = args.prefix
    
    # Submit input files and then the job file.
    job_params = client.submit_files(job_params)
    job_file = client.submit_job(job_params)
    logger.info(f"Job file created: {job_file}")
    
    # Download results by polling for each file until available.
    downloaded_files = client.download_results(
        output_dir=args.output_dir,
        timeout=args.timeout,
        interval=args.interval
    )
    logger.info(f"Downloaded result files: {downloaded_files}")


if __name__ == "__main__":
    main()
