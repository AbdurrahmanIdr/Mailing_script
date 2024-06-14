import os
from datetime import datetime
from pathlib import Path


def format_file_size(size_in_bytes):
    """
       Format the file size in bytes to a human-readable string.

       Args:
           size_in_bytes (float): File size in bytes.

       Returns:
           str: Formatted file size with units.
       """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_in_bytes < 1024.0:
            break
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.2f} {unit}"


def datetimeformat(value):
    """
       Format the given timestamp to a string using the specified format.

       Args:
           value (float): Timestamp.

       Returns:
           str: Formatted datetime string.
       """
    format_time: str = '%Y-%m-%d %H:%M:%S'
    return datetime.fromtimestamp(value).strftime(format_time)


def get_sorted_files(directory):
    """
    Get a sorted list of directories and files in the given directory.

    Args:
        directory (str): The directory path.

    Returns:
        tuple: Sorted list of directories and files, current directory.
    """

    directory = Path(directory)
    items = []

    try:
        items = list(directory.iterdir())
    except (PermissionError, FileNotFoundError):
        if directory.parent:
            directory = directory.parent
            items = list(directory.iterdir())

    dirs = []  # List to store unique directory names
    files = []  # List to store file names

    # Set to store directory names to avoid repetition
    seen_dirs = set()
    seen_files = set()

    # Add link to parent directory if not at the root
    if directory.name != 'data':
        dirs.append("..")
        seen_dirs.add("..")

    for item in items:
        # Check if the item is either a directory or a file
        if item.is_dir() or item.is_file():
            # Resolve symbolic links to get the real path
            real_path = item.resolve()
            # Get the name of the item
            name = real_path.name

            # Exclude files and folders that start with a dot
            if not name.startswith('.'):
                # Exclude the current directory from the list
                if real_path != directory:
                    # Check if the item is a directory
                    if real_path.is_dir():
                        # Check if the directory name is not repeated
                        if name not in seen_dirs:
                            # Append the directory name to the list of directories
                            dirs.append(name)
                            # Add the directory name to the set of seen directories
                            seen_dirs.add(name)
                            
                    # Check if the item is a file
                    elif real_path.is_file():
                        # Check if the directory name is not repeated
                        if name not in seen_files:
                            # Append the file name to the list of files
                            files.append(name)
                            # Add the file name to the set of seen files
                            seen_files.add(name)
                            
    return sorted(list(seen_dirs)) + sorted(list(seen_files)), directory



def get_file_info(file_path):
    """
        Get information about a file.

        Args:
            file_path (Path): Path to the file.

        Returns:
            dict: File information dictionary.
        """
    stat_info = os.stat(file_path)

    file_info = {
        "File Path": str(file_path),
        "File Size": format_file_size(stat_info.st_size),
        "Last Modified": stat_info.st_mtime,
        "Is Directory": os.path.isdir(file_path),
        "Is File": os.path.isfile(file_path),
        "File Extension": str(file_path).split('.')[-1],
        "File Permissions": oct(stat_info.st_mode)[-3:],
        "Path Components": file_path.parts,
    }

    return file_info


def query_string(folder, db_found):
    split_files = [f.split('_')[0] for f in os.listdir(folder) if f.endswith('.pdf')]
    db_ippis = [user.ippis for user in db_found]

    file_users = set(split_files)
    db_users = set(db_ippis)

    active_found = file_users & db_users  # in db and pdf files
    inactive = file_users - db_users  # in pdf files but not in db
    unknown = db_users - file_users  # in db but not in pdf files

    return active_found, inactive, unknown
