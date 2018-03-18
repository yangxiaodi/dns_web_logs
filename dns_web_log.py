#!/usr/local/bin/ python
# -*- coding: utf-8 -*-

__author__ = 'yangxiaodi'

import re
import multiprocessing
from datetime import datetime, timedelta, timezone
from dnslib import QTYPE, zoneresolver
from dnslib.server import DNSServer, DNSLogger
from flask import request, Flask, render_template, make_response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.routing import BaseConverter
import urllib.parse

class RegexConverter(BaseConverter):
    def __init__(self, map, *args):
        self.map = map
        self.regex = args[0]

app = Flask(__name__)
app.url_map.converters['regex'] = RegexConverter
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///./web.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


ADMIN_DOMAIN = 'admin.xxx.pw'# 记录管理的域名
DNS_DOMAIN = 'xxx.pw' # 做dns记录的域名
NS1_DOMAIN = 'ns1.ddd.com' # NS域名
NS2_DOMAIN = 'ns2.ddd.com'
SERVER_IP = 'xxx.xxx.xxx.xxx'# 服务器外网地址


class Web_logs(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.VARCHAR(200))
    ua = db.Column(db.VARCHAR(200))
    host = db.Column(db.VARCHAR(100))
    times = db.Column(db.VARCHAR(100))

    def __init__(self, url, ua, host, times):
        self.url = url
        self.ua = ua
        self.host = host
        self.times = times

    def __repr__(self):
        return '<Url %r>' % self.url


class Dns_logs(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.VARCHAR(200))
    host = db.Column(db.VARCHAR(200))
    qtype = db.Column(db.VARCHAR(100))
    times = db.Column(db.VARCHAR(100))

    def __init__(self, url, host, qtype, times):
        self.url = url
        self.host = host
        self.qtype = qtype
        self.times = times

    def __repr__(self):
        return '<Url %r>' % self.url


class Logger(DNSLogger):
    '''
    设置记录的域名长度大于9
    '''
    def log_request(self, handler, request):
        utc_dt = datetime.utcnow().replace(tzinfo=timezone.utc)
        times = utc_dt.astimezone(timezone(timedelta(hours=8)))
        global DNS_DOMAIN
        domain = request.q.qname.__str__()
        if domain.endswith(DNS_DOMAIN + '.') and len(domain) > 9 and ADMIN_DOMAIN not in domain:
            udomain = re.search(r'\.?([^\.]+)\.%s\.' % DNS_DOMAIN, domain)
            if udomain:
                result = Dns_logs(url=domain[0:-1], host=str(handler.client_address[0])+":"+str(handler.client_address[1]), qtype=QTYPE[request.q.qtype], times=times)
                db.session.add(result)
                db.session.commit()


def use_dnslog():
    global DNS_DOMAIN,NS2_DOMAIN,NS1_DOMAIN,SERVER_IP
    ZoneResolver = zoneresolver.ZoneResolver
    #下面的zone的几行不能缩进
    zone = '''
*.{dnsdomain}.       IN      NS      {ns1domain}.
*.{dnsdomain}.       IN      NS      {ns2domain}.
*.{dnsdomain}.       IN      A       {serverip}
{dnsdomain}.       IN      A       {serverip}
'''.format(dnsdomain=DNS_DOMAIN, ns1domain=NS1_DOMAIN, ns2domain=NS2_DOMAIN, serverip=SERVER_IP)
    resolver = ZoneResolver(zone, True)
    logger = Logger()
    print("Starting Zone Resolver (%s:%d) [%s]" % ("*", 53, "UDP"))
    udp_server = DNSServer(resolver, port=53, address='', logger=logger)
    udp_server.start()


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
    Referer = request.headers.get('Referer') or ''
    utc_dt = datetime.utcnow().replace(tzinfo=timezone.utc)
    times = utc_dt.astimezone(timezone(timedelta(hours=8)))
    result = Web_logs(url=url, ua=ua+"|||"+Referer, host=host, times=times)
    db.session.add(result)
    db.session.commit()
    return '<body>Success</body>'


@app.route('/admin/show_<any(web,dns):page_name>')
def test(page_name):
    admin_url = request.url
    if ADMIN_DOMAIN == urllib.parse.urlparse(admin_url).netloc:
        token = request.cookies.get('token')
        if token == "9988817y222hsbdvttr55qq":
            page = int(request.args.get('page')) if request.args.get('page') else 1

            page = int(page - 1) * 10
            if page_name == "web":
                result = Web_logs.query.filter_by().order_by(Web_logs.id.desc()).limit(10).offset(page).all()
                data = [dict(url=row.url, ua=row.ua, host=row.host, times=row.times) for row in result]
                web_number = Web_logs.query.count()
                number = int(web_number / 10) + 1
                return render_template("show_web.html", datas=data, num=number)
            if page_name == "dns":
                result = Dns_logs.query.filter_by().order_by(Dns_logs.id.desc()).limit(10).offset(page).all()
                data = [dict(url=row.url, host=row.host, qtype=row.qtype, times=row.times) for row in result]
                dns_number = Dns_logs.query.count()
                number = int(dns_number / 10) + 1
                return render_template("show_dns.html", datas=data, num=number)
        else:
            return "error"
    else:
        return "error"


@app.route('/admin/setcookie')
def setcookie():
    outdate = datetime.today() + timedelta(days=30)
    response = make_response('Hello World')
    response.set_cookie('token', '9988817y222hsbdvttr55qq',expires=outdate)
    return response


if __name__ == '__main__':
    p = multiprocessing.Process(target=use_dnslog)
    p.daemon = True
    p.start()
    app.run('0.0.0.0',port=80)