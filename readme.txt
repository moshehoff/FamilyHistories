
docker build --no-cache -t familyhistories .
docker run --rm familyhistories

cd site
npx quartz build --serve
http://localhost:8080 