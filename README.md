# Voice Harbor Client

A Python client for interacting with the [Voice Harbor API](#). This client handles job creation, file uploads, and result downloads through secure signed URLs. It supports audio file formats.

## Features

- **Job Management:** Create a new job on the Voice Harbor server.
- **File Uploads:** Upload audio and YAML files concurrently using signed URLs.
- **Result Downloading:** Poll for and download processed results.
- **CLI Support:** Execute the client as a command-line tool with various options.

## Supported File Formats

The client currently supports the following file types as stereo and mono:

- `.wav`
- `.mp3`
- `.flac`
- `.ogg`
- `.m4a`

## Requirements

- Python 3.6 or higher

### Python Dependencies

The client depends on the following Python packages:
- `requests`
- `PyYAML`
- `tqdm`

You can install these dependencies with pip. For example, in your terminal you might run:
  
  pip install requests pyyaml tqdm

## Installation

### From Source

1. Clone the repository from GitHub.
2. Change into the project directory.
3. Install the package in editable mode using pip:

```bash
  pip install -e .
```

## Usage

### Command-Line Interface (CLI)

After installation, the CLI is available as `voice-harbor-client`. The tool accepts several parameters:

- **--base-url:** (Required) The base URL of the Voice Harbor API.
- **--token:** (Required) Your authorization token.
- **--inputs-dir:** (Required) Directory containing input files to be processed.
- **--output-dir:** Directory where the downloaded results will be stored (default: `./results`).
- **--timeout:** Timeout in seconds for waiting on file availability (default: 600).
- **--interval:** Polling interval in seconds to check file status (default: 10).
- **--agents:** List of agents to use for processing (default: `health-generic`), required for `advanced` model.
- **--prefix:** An optional prefix to include files containing prefix in their name.

**Example Usage:**

You can run the tool from the command line like this:

```bash
python voice_harbor_client.py \
    --base-url https://voiceharbor.ai \
    --token YOUR_AUTH_TOKEN \
    --inputs-dir /path/to/input_files \
    --output-dir /path/to/output_results \
    --timeout 600 \
    --interval 10 \
    --agents health-generic clinical \
    --prefix "optional-prefix"
```

### Programmatic Admin Usage

You will be provided with a ADMIN token by sales@nijta.com?. 

Generate a developer token: 
```python
from client import VoiceHarborClient
BASE_URL = "https://voiceharbor.ai"
admin_token = "TOKEN"
usage_token = VoiceHarborClient.create_developer_token(BASE_URL, admin_token)
# Received developer token stored below: ./credentials/VoiceHarbor_Developer.credential.<date>.yaml.
```
#### Get Job's and finilized results overview

List all developer tokens generated by admin.

```python
usage_tokens = VoiceHarborClient.get_developer_tokens(BASE_URL, ADMIN_TOKEN)
```
List total global usage generated by all developer tokens.

```python
BASE_URL = "https://voiceharbor.ai"
for token_metadata in usage_tokens:
    jobs_metadata = VoiceHarborClient.get_jobs(BASE_URL, token_metadata['usage_token'])
    for job_metadata in jobs_metadata:
        print (VoiceHarborClient.get_job_content(BASE_URL, usage_token, job_metadata['job_id']))
```

The output is a JSON response represented as a dictionary with the following fields:

```bash
id: A unique integer identifier for the audio record.
job_id: A unique string representing the job associated with the audio file.
file_name: The name of the audio file.
audio_duration: The duration of the audio file in seconds.
created_at: An ISO 8601 timestamp indicating when the audio file was created.
```

### Programmatic Developer Usage

The client can also be used as a Python module. For example:

#### Immediate Job Submission and Results Download

```python
BASE_URL = "https://voiceharbor.ai"
usage_token = "TOKEN"
# Create a new job on the server via the class method.
# Create a new job immediately.
job_id = VoiceHarborClient.create_job(BASE_URL, usage_token)
print(f"Job created with ID: {job_id}")

# Initialize the client with the new job_id and input directory.
client = VoiceHarborClient(
    base_url=BASE_URL,
    job_id=job_id,
    token=AUTH_TOKEN,
    inputs_dir="./inputs"
)

# Build job parameters (e.g., list of agents and any other details).
job_params = {
    "agents": ["health-generic"],
    "files": []  # The submit_files method will append uploaded file names.
}

# Upload input files.
job_params = client.submit_files(job_params)

# Immediately submit the job file (YAML)
job_file = client.submit_job(job_params)
print(f"Job file submitted: {job_file}")

# Wait for and download the processed results.
downloaded_results = client.download_results(output_dir="./results")
print("Downloaded results:", downloaded_results)
```
#### Delayed Job Start
```python
BASE_URL = "https://voiceharbor.ai"
usage_token = "TOKEN"

# Create a new job.
job_id = VoiceHarborClient.create_job(BASE_URL, usage_token)
print(f"Job created with ID: {job_id}")

# Initialize the client with the new job_id.
client = VoiceHarborClient(
    base_url=BASE_URL,
    job_id=job_id,
    token=AUTH_TOKEN,
    inputs_dir="./inputs"
)

# Upload input files without submitting the job file immediately.
job_params = {
    "agents": ["health-generic"],
    "files": []
}
job_params = client.submit_files(job_params)

# Store the job parameters locally for later submission.
job_params_file = f"{job_id}_job_params.json"
with open(job_params_file, "w") as f:
    json.dump(job_params, f)
print(f"Job parameters stored for later submission: {job_params_file}")
```
Simulate a delay (e.g., waiting until tomorrow to submit the job file).
```python
# Later, load the stored job parameters and submit the job file.
with open(job_params_file, "r") as f:
    delayed_job_params = json.load(f)
job_file = client.submit_job(delayed_job_params)
print(f"Delayed job file submitted: {job_file}")

# Download the results when processing is complete.
downloaded_results = client.download_results(output_dir="./results")
print("Downloaded results:", downloaded_results)
```
#### Scheduled Download Use Case
In this scenario, you create and submit a job as usual. The job file (a YAML file named using the job_id) is saved locally. Then, at a later time (for example, the next day), you reinitialize your client using the same job_id and trigger the download of results.

***Step 1:*** Job Creation and Submission (Today).
Run the following script to create a job, upload input files, and submit the job file. This script also stores the job parameters locally (optionally) and writes the YAML file (named with the job_id) which can be used later to trigger the download.

```python
BASE_URL = "https://voiceharbor.ai"
usage_token = "TOKEN"
# Create a new job.
job_id = VoiceHarborClient.create_job(BASE_URL, usage_token)
logger.info(f"Job created with ID: {job_id}")

# Initialize the client with the new job_id and input directory.
client = VoiceHarborClient(
    base_url=BASE_URL,
    job_id=job_id,
    token=AUTH_TOKEN,
    inputs_dir="./inputs"  # Directory containing files to be uploaded.
)

# Build job parameters. For example, specify which agents to use.
job_params = {
    "agents": ["health-generic"],
    "files": []  # The submit_files method will append the names of uploaded files.
}

# Upload input files.
job_params = client.submit_files(job_params)

# Submit the job file (this writes a YAML file named as {job_id}.yaml).
job_file = client.submit_job(job_params)
logger.info(f"Job file submitted and saved locally as: {job_file}")  # <--- JOB_ID
```
***Step 2:*** Scheduled Download (Tomorrow)

When you're ready to download the results—say, tomorrow—you can run a separate script that reinitializes the client with the known job_id (from the YAML file name) and then calls the download function to retrieve the processed results.

```python
BASE_URL = "https://voiceharbor.ai"
usage_token = "TOKEN"

# Use a existing job_id.
JOB_ID = "<job_id>" # <--- JOB_ID 

# Reinitialize the client with the same job_id (inputs_dir is not required for download).
client = VoiceHarborClient(
    base_url=BASE_URL,
    job_id=JOB_ID,
    token=AUTH_TOKEN,
    inputs_dir=""  # No need for input files when only downloading results.
)

# Download the processed results.
downloaded_results = client.download_results(output_dir="./results")
logger.info(f"Downloaded results for job {JOB_ID}: {downloaded_results}")
```
