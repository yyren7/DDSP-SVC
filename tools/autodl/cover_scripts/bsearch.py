# Bilibili video search with the instance's login cookies: python bsearch.py "keyword" [pages]
import sys, json, time, re, hashlib, urllib.parse, urllib.request, http.cookiejar
cj = http.cookiejar.MozillaCookieJar('/root/autodl-tmp/DDSP-SVC/.autodl/bilibili_cookies.txt'); cj.load(ignore_discard=True, ignore_expires=True)
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36', 'Referer': 'https://www.bilibili.com/'}
def get(url):
    return json.load(op.open(urllib.request.Request(url, headers=UA), timeout=20))
nav = get('https://api.bilibili.com/x/web-interface/nav')['data']['wbi_img']
key = ''.join(u.rsplit('/', 1)[1].split('.')[0] for u in (nav['img_url'], nav['sub_url']))
TAB = [46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,29,28,14,39,12,38,41,13,37,48,7,16,24,55,40,61,26,17,0,1,60,51,30,4,22,25,54,21,56,59,6,63,57,62,11,36,20,34,44,52]
mix = ''.join(key[i] for i in TAB)[:32]
def search(kw, page=1):
    p = {'search_type': 'video', 'keyword': kw, 'page': page, 'wts': int(time.time())}
    q = urllib.parse.urlencode(sorted(p.items())).replace('+', '%20')
    q += '&w_rid=' + hashlib.md5((q + mix).encode()).hexdigest()
    return get('https://api.bilibili.com/x/web-interface/wbi/search/type?' + q)
kw = sys.argv[1]; pages = int(sys.argv[2]) if len(sys.argv) > 2 else 1
for pg in range(1, pages + 1):
    r = search(kw, pg)
    if r.get('code'): print('ERR', r.get('code'), r.get('message')); break
    for v in r['data'].get('result') or []:
        t = re.sub('<[^>]+>', '', v['title'])
        print(f"{v['bvid']}\t{v['duration']}\t{v['play']}\t{v['author']}\t{t}")
