#!/bin/sh
set -e
npx ng build --configuration=production
rsync -av --exclude=.htaccess --delete dist/mtd/ michifor@michif.org:dictionary.michif.org.new/
