#!/usr/bin/env bash
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'
rand=`cat date | md5sum | env LC_CTYPE=C tr -dc 'a-z0-9' | fold -w 8 | head -n 1`
ci_id="ci$rand"
docker_compose_file="docker-compose.yml"

cleanup () {
  docker-compose -f $docker_compose_file -p $ci_id down
  docker network rm "${ci_id}_default" || true
}
trap 'cleanup ; printf "${RED}Tests Failed For Unexpected Reasons${NC}\n"' HUP INT QUIT PIPE TERM
docker-compose -f $docker_compose_file -p ${ci_id} pull
docker-compose -f $docker_compose_file -p ${ci_id} build

docker-compose -f $docker_compose_file -p ${ci_id} up -d db
sleep 2
docker-compose -f $docker_compose_file -p ${ci_id} up -d db-migrate
sleep 2
docker-compose -f $docker_compose_file -p ${ci_id} up -d

if [ $? -ne 0 ] ; then
  printf "${RED}Docker Compose Failed${NC}\n"
  cleanup
  exit -1
fi
TEST_EXIT_CODE=`docker wait ${ci_id}_test-integrational_1`

printf "${YELLOW}Collecting logs...${NC}\n"
mkdir -p logs
docker logs ${ci_id}_db_1 &> ./logs/db
docker logs ${ci_id}_db-migrate_1 &> ./logs/db-migrate
docker logs ${ci_id}_test-integrational_1 &> ./logs/test-integrational

printf "${YELLOW}Collecting report...${NC}\n"
docker cp ${ci_id}_test-integrational_1:/app/report_int.xml ./

printf "${YELLOW}Tests output:${NC}\n"
docker logs ${ci_id}_test-integrational_1
if [ -z ${TEST_EXIT_CODE} ] || [ "$TEST_EXIT_CODE" -ne 0 ] ; then
  printf "${RED}Tests Failed${NC} - Exit Code: $TEST_EXIT_CODE\n"
else
  printf "${GREEN}Tests Passed${NC}\n"
fi
cleanup
exit $TEST_EXIT_CODE
