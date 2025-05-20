
docker build -t familyhistories .


cd site
npx quartz build --serve
http://localhost:8080 