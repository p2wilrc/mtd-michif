#!/bin/sh
set -e
npx ng build --configuration=production
rsync -av --exclude=.htaccess --delete dist/mtd/ michif.org:dictionary.michif.org.new/
