import shutil
from pathlib import Path


def check_single_pptx_in_folder(folder_path):
    folder = Path(folder_path)
    pptx_files = list(folder.glob("*.pptx"))

    if len(pptx_files) == 1:
        print(f"Found exactly one PowerPoint file: {pptx_files[0]}")
        return pptx_files[0]
    elif len(pptx_files) > 1:
        raise ValueError("Error: More than one PowerPoint file found.")
    else:
        raise ValueError("Error: No PowerPoint files found.")


if __name__ == "__main__":
    input_folder = "input"
    output_folder = "workingdir"
    pptx_file = check_single_pptx_in_folder(input_folder)
    Path(output_folder).mkdir(parents=True, exist_ok=True)
    shutil.copy(pptx_file, Path(output_folder) / "powerpoint.pptx")
    print(f"Copied {pptx_file} to {output_folder}/powerpoint.pptx")
