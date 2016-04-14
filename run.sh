#
# Start hexblog if not started already
# On Netease cloud container, add crontab task to run it periodically:
# 	# crontab -e
#	add line '* *    *   *   *   /work/hexblog/run.sh'
#


HEXBLOG_ROOT="`dirname $0`"
HEXBLOG_LOG_FILE="${HEXBLOG_ROOT}/log"


if [ `ps -ef | grep python | grep manage.py | wc -l` -lt 1 ]; then
	cd ${HEXBLOG_ROOT}
	./manage.py runserver --host 0.0.0.0 --port 80 > ${HEXBLOG_LOG_FILE} 2>&1 &
	echo 'Hexblog started'
fi


