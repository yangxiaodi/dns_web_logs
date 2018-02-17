#!/usr/local/bin/ python
# -*- coding: utf-8 -*-

__author__ = 'yangxiaodi'

import re
import os
import coloredlogs
import logging
import sqlite3
import multiprocessing
from datetime import datetime, timedelta, timezone
from dnslib import QTYPE, zoneresolver
from dnslib.server import DNSServer, DNSLogger
from flask import request, Flask, g, render_template
from werkzeug.routing import BaseConverter


DNS_DOMAIN = 'xxx.pw' # 做dns记录的域名
NS1_DOMAIN = 'ns1.ddd.com' # NS域名
NS2_DOMAIN = 'ns2.ddd.com'
SERVER_IP = 'xxx.xxx.xxx.xxx'# 服务器外网地址


class RegexConverter(BaseConverter):
    def __init__(self, map, *args):
        self.map = map
        self.regex = args[0]


app = Flask(__name__)
app.url_map.converters['regex'] = RegexConverter


def getModuleLogger(moduleName):
    logging.basicConfig(filename= moduleName + '.log',format='[%(asctime)s-%(filename)s-%(levelname)s:%(message)s]', level = logging.DEBUG,filemode='a',datefmt='%Y-%m-%d %I:%M:%S %p')
    logger = logging.getLogger(moduleName)
    logger.setLevel(logging.INFO)
    coloredlogs.install(level='INFO', logger=logger)
    return logger


class Logger(DNSLogger):
    def log_request(self, handler, request):
        utc_dt = datetime.utcnow().replace(tzinfo=timezone.utc)
        times = utc_dt.astimezone(timezone(timedelta(hours=8)))
        loggings = getModuleLogger("dns_web_logs")
        global DNS_DOMAIN
        domain = request.q.qname.__str__()
        if domain.endswith(DNS_DOMAIN + '.'):
            udomain = re.search(r'\.?([^\.]+)\.%s\.' % DNS_DOMAIN, domain)
            if udomain:
            # if udomain and udomain != ADMIN_DOMAIN:#当要启用记录管理的域名就使用这个
                loggings.info((domain,
                              str(handler.client_address[0])+":"+str(handler.client_address[1]),
                              QTYPE[request.q.qtype]))
            conn = Sqlite3_Database().Crete_Database()
            conn.execute('insert into dns_logs (url, host, qtype, times) values (:dns_url, :dns_host, :dns_qtype, :dns_times)' , {'dns_url':domain, 'dns_host':str(handler.client_address[0])+":"+str(handler.client_address[1]), 'dns_qtype':QTYPE[request.q.qtype], 'dns_times':times})
            conn.commit()
            conn.close()


def use_dnslog():
    global DNS_DOMAIN,NS2_DOMAIN,NS1_DOMAIN,SERVER_IP
    ZoneResolver = zoneresolver.ZoneResolver
    #下面的zone的几行不能缩进
    zone = '''
*.{dnsdomain}.       IN      NS      {ns1domain}.
*.{dnsdomain}.       IN      NS      {ns2domain}.
*.{dnsdomain}.       IN      A       {serverip}
{dnsdomain}.       IN      A       {serverip}
'''.format(
        dnsdomain = DNS_DOMAIN, ns1domain = NS1_DOMAIN,
        ns2domain = NS2_DOMAIN, serverip= SERVER_IP)
    resolver = ZoneResolver(zone, True)
    logger = Logger()
    print("Starting Zone Resolver (%s:%d) [%s]" % ("*", 53, "UDP"))
    udp_server = DNSServer(resolver,
                           port=53,
                           address='',
                           logger=logger)
    udp_server.start()


class Sqlite3_Database(object):

    def Crete_Database(self):
        if not os.path.exists('./web.db'):
            conn = sqlite3.connect('./web.db')
            self.Create_Table(conn)
        else:
            conn = sqlite3.connect('./web.db')
        return conn


    def Create_Table(self,conn):
        '''
        创建数据库表 dns_logs
        '''
        create_table_sql = '''
                        CREATE TABLE `dns_logs` (
                           `id` INTEGER  NOT NULL,
                           `url` varchar(200)  NULL,
                           `host` varchar(100)  NULL,
                           `qtype` varchar(100)  NULL,
                           `times` varchar(100)  NULL,
                            PRIMARY KEY (`id`)
                            )
        '''
        create_table_sql1 = '''
                        CREATE TABLE `web_logs` (
                           `id` INTEGER  NOT NULL,
                           `url` varchar(200)  NULL,
                           `ua` varchar(200)  NULL,
                           `host` varchar(100)  NULL,
                           `times` varchar(100)  NULL,
                            PRIMARY KEY (`id`)
                            )
        '''

        conn.execute(create_table_sql)
        conn.commit()
        conn.execute(create_table_sql1)
        conn.commit()


@app.before_request
def before_request():
    g.db = Sqlite3_Database().Crete_Database()


@app.teardown_request
def teardown_request(exception):
    if hasattr(g, 'db'):
        g.db.close()


@app.route('/<regex(".*"):_>')
def Hello_World(_):
    if _ == "favicon.ico":
        return 'error'
    url = request.url
    global DNS_DOMAIN
    if DNS_DOMAIN not in url:
        return 'error'
    host = request.remote_addr
    ua = request.headers.get('User-Agent') or ''
    utc_dt = datetime.utcnow().replace(tzinfo=timezone.utc)
    times = utc_dt.astimezone(timezone(timedelta(hours=8)))
    g.db.execute('insert into web_logs (url, ua, host, times) values (:web_url, :web_ua, :web_host, :web_times)' , {'web_url':url, 'web_ua':ua, 'web_host':host, 'web_times':times})
    g.db.commit()
    return '<body>Success</body>'


@app.route('/admin/show_<any(web,dns):page_name>')
def test(page_name):
    if page_name == "web":
        cur = g.db.execute('select url, ua, host, times from web_logs')
        data = [dict(url=row[0], ua=row[1], host=row[2], times=row[3]) for row in cur.fetchall()]
        return render_template("show_web.html", datas=data)
    if page_name == "dns":
        cur = g.db.execute('select url, host, qtype, times from dns_logs')
        data = [dict(url=row[0], host=row[1], qtype=row[2], times=row[3]) for row in cur.fetchall()]
        return render_template("show_dns.html", datas=data)


if __name__ == '__main__':
    p = multiprocessing.Process(target=use_dnslog)
    p.daemon = True
    p.start()
    app.run('0.0.0.0',port=80)
