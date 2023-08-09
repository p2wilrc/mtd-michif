DATE=$(date +%Y%m%d)
npx ng build --configuration=production --base-href=/mtd-${DATE}/ && rsync --delete -av dist/mtd/ 192.168.1.103:/var/www/michif/html/mtd-${DATE}/
