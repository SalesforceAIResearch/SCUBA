from huggingface_hub import snapshot_download

# local_dir = "/fsx/sfr/data/yutong/GUI-Owl-7B/"
# repo_id = "mPLUG/GUI-Owl-7B"
# snapshot_download(
#     repo_id=repo_id,
#     local_dir=local_dir,
# )


local_dir = "/fsx/sfr/data/yutong/UI-TARS-2B-SFT/"
repo_id = "ByteDance-Seed/UI-TARS-2B-SFT"
snapshot_download(
    repo_id=repo_id,
    local_dir=local_dir,
)
