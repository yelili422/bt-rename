#!/usr/bin/env bash

find "GIRLS und PANZER" -maxdepth 1 -type f ! -name ".DS_Store" \
    -o -type d -iname "Scan*" \
    -o -type d -iname "Specials" \
    -o -type d -iname "SPs" \
    -o -type d -iname "Bonus" \
    -o -type d -iname "CDs" \
    -o -type d -name "*特典*" \
    | sort \
    | bt-rename
