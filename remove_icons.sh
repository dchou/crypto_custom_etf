# A script to remove bad 'Icon?' files from a git repository

# Steps:
# 1. Run this: chmod +x remove_icons.sh
# 2. Run this: ./remove_icons.sh

#!/bin/bash

# Remove bad sha1 files from .git/objects
find .git/objects -name 'Icon?' -type f -delete

# Remove bad references from .git/refs, .git/logs, and their subdirectories
find .git/refs .git/logs -name 'Icon?' -type f -delete

# Check for consistency in the repository
git fsck --full

# Find and delete any remaining 'Icon?' files in the repository
find . -name 'Icon?' -type f -delete

# Add changes to staging
git add .

# Commit the changes
git commit -m "Removed Icon? files causing issues"
