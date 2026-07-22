"""
submit_to_aihub.py -- compile and profile the CAN IDS autoencoder on a real,
hosted Qualcomm device via AI Hub.

Requires: model.onnx (from convert_to_onnx.py), qai-hub installed and
configured with your API token.

IMPORTANT: replace DEVICE_NAME below with the exact string printed by the
device-search snippet (don't guess it) before running this.

Usage:
    python submit_to_aihub.py
"""

import qai_hub as hub

from features import FEATURE_NAMES

N_FEATURES = len(FEATURE_NAMES)

# Replace with the exact string found via:
#   for d in hub.get_devices():
#       if "8775" in d.name: print(d.name)
DEVICE_NAME = "REPLACE_ME_WITH_EXACT_DEVICE_STRING"


def main():
    device = hub.Device(DEVICE_NAME)
    print(f"Targeting device: {device.name}")

    print("\nSubmitting compile job...")
    compile_job = hub.submit_compile_job(
        model="model.onnx",
        device=device,
        input_specs=dict(x=(1, N_FEATURES)),
    )
    print(f"Compile job submitted: {compile_job.job_id}")
    print("Waiting for compile job to finish...")
    compile_job.wait()
    print(f"Compile job status: {compile_job.get_status()}")

    target_model = compile_job.get_target_model()

    print("\nSubmitting profile job...")
    profile_job = hub.submit_profile_job(
        model=target_model,
        device=device,
    )
    print(f"Profile job submitted: {profile_job.job_id}")
    print("Waiting for profile job to finish...")
    profile_job.wait()
    print(f"Profile job status: {profile_job.get_status()}")

    print("\nView full results (including latency, memory, NPU utilization) at:")
    print(f"  Compile job: https://workbench.aihub.qualcomm.com/jobs/{compile_job.job_id}/")
    print(f"  Profile job: https://workbench.aihub.qualcomm.com/jobs/{profile_job.job_id}/")


if __name__ == "__main__":
    main()
