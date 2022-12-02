#!/bin/bash

docker build -f "Dockerfile" -t youtubedl:latest "." 
docker run -it --rm -v youtube-dl_data:/config -p 8080:8080 --name youtube-dl -v $(pwd)/downloads:/downloads -v $(pwd)/root/app/webserver:/app/webserver -e youtubedl_webui=true youtubedl:latest