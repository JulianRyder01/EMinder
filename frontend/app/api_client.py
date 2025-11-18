# frontend/app/api_client.py
# ========================== START: MODIFICATION (File Splitting) ==========================
# DESIGNER'S NOTE:
# This new file acts as the dedicated API client, or the "service layer".
# It encapsulates all HTTP requests to the backend, handling network-level errors
# and returning structured data. This decouples the UI logic from the details of API communication.

import requests
import os
import json
from urllib.parse import quote

from .config import config

def check_backend():
    """Checks the backend service status."""
    try:
        response = requests.get(config.ROOT_URL, timeout=2)
        if response.status_code == 200:
            return "🟢 后端服务正常"
        return f"🟡 后端服务异常 (状态码: {response.status_code})"
    except requests.ConnectionError:
        return "🔴 后端服务未连接"

def get_templates_info():
    """Fetches template metadata from the backend."""
    response = requests.get(config.TEMPLATES_INFO_URL)
    response.raise_for_status()
    return response.json()

def get_subscribers():
    """Fetches the list of subscribers from the backend."""
    response = requests.get(config.SUBSCRIBERS_URL)
    response.raise_for_status()
    return response.json().get("subscribers", [])

def add_subscriber(email, remark_name):
    """Posts a new subscriber to the backend."""
    response = requests.post(config.SUBSCRIBERS_URL, json={"email": email, "remark_name": remark_name})
    response.raise_for_status()
    return response.json()

def delete_subscriber(email):
    """Deletes a subscriber from the backend."""
    encoded_email = quote(email)
    response = requests.delete(f"{config.SUBSCRIBERS_URL}/{encoded_email}")
    response.raise_for_status()
    return response.json()

def get_jobs():
    """Fetches the list of scheduled jobs from the backend."""
    response = requests.get(config.JOBS_URL)
    response.raise_for_status()
    return response.json().get("jobs", [])

def get_job_details(job_id):
    """Fetches the details of a single job by its ID."""
    response = requests.get(f"{config.JOBS_URL}/{job_id}")
    response.raise_for_status()
    return response.json().get("job")

def cancel_job(job_id):
    """Sends a request to cancel a scheduled job by its ID."""
    response = requests.delete(f"{config.JOBS_URL}/{job_id.strip()}")
    response.raise_for_status()
    return response.json()

# ========================== START: MODIFICATION (Feature Addition) ==========================
# DESIGNER'S NOTE: Added this function to call the new backend endpoint for immediately running a job.
def run_job_now(job_id: str):
    """Sends a request to run a scheduled job immediately."""
    response = requests.post(f"{config.JOBS_URL}/{job_id.strip()}/run")
    response.raise_for_status()
    return response.json()

def post_email_request(url, form_data, attachment_files_list):
    """
    Handles posting email requests that may contain file attachments (multipart/form-data).
    This is used for both 'send-now' and 'schedule-once'.
    """
    files_to_send = []
    if attachment_files_list:
        try:
            for file_path in attachment_files_list:
                file_info = (
                    'attachments',
                    (os.path.basename(file_path), open(file_path, "rb"), 'application/octet-stream')
                )
                files_to_send.append(file_info)
        except Exception as e:
            # Clean up any opened files before raising
            for _, file_tuple in files_to_send:
                file_tuple[1].close()
            raise IOError(f"无法打开附件文件。请检查文件是否存在或权限是否正确。详情: {e}")

    try:
        response = requests.post(url, data=form_data, files=files_to_send)
        response.raise_for_status()
        return response.json()
    finally:
        # Ensure all file handles are closed after the request
        if files_to_send:
            for _, file_tuple in files_to_send:
                file_tuple[1].close()

def post_cron_job(payload):
    """Posts a new cron job schedule to the backend."""
    response = requests.post(config.SCHEDULE_CRON_URL, json=payload)
    response.raise_for_status()
    return response.json()

def update_job(job_id, payload):
    """Puts an update for an existing job to the backend."""
    response = requests.put(f"{config.JOBS_URL}/{job_id}", json=payload)
    response.raise_for_status()
    return response.json()

# ========================== END: MODIFICATION (File Splitting) ============================