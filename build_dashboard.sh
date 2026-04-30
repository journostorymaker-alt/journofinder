#!/bin/bash
# Copy the database into the dashboard folder before deployment.
# The dashboard's index.html fetches ./data/journalists.db, so for a static deploy
# we need the data folder accessible alongside the HTML file.
set -e

cd "$(dirname "$0")"
mkdir -p dashboard/data
cp data/journalists.db dashboard/data/journalists.db
echo "Database copied to dashboard/data/journalists.db ($(du -h dashboard/data/journalists.db | cut -f1))"
echo "You can now deploy the dashboard/ folder to Netlify, GitHub Pages, or any static host."
