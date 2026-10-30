# 检索工具缺失时的兜底

`offline-degradation.md` 处理「没有网络」。本文件处理另一种常见情况：**网络是通的，但会话里没有可用的搜索工具**。

两者看起来都是「搜不了」，但处理方式不同——前者只能降级，后者往往还能救，因为公开搜索端点不需要 API key。

**一句话分界：搜索工具报的是凭据错误（`no API key`、`401`、`未配置`），就进本文件；报的是超时、DNS 失败、连不上，就进 `offline-degradation.md`。** 误判成「离线」会让用户白等一个本来能答的问题；误判成「没工具」会让用户白试三个端点。两边都失败时，按 `offline-degradation.md` 带记录降级。

B 形态（单文件）也收录了本文件，所以「没工具」这条路径在只拿到一段文本的宿主上同样可用。

## 这些结论的适用范围

**本文件里的端点实测结果，来自一次具体的测试环境，不是永久保证。** 公开端点随时可能改版、加验证、封禁脚本请求。

所以用法是：**先把下面当候选，用之前现场验一次**。验证方法很简单——拿一个已知答案的查询试一次，检查返回内容里有没有关键词。验不通就换下一个端点，全都验不通才降级。

不要因为本文件写了「可用」就直接相信它可用，也不要因为某个端点在别的环境不可用就认为它永远不可用。

## 本文导航

- [先判：是没网，还是没工具](#先判是没网还是没工具)
- [调用顺序与上限](#调用顺序与上限)
- [实测可用的公开端点](#实测可用的公开端点)
- [端点的实测结论](#端点的实测结论)
- [怎么调（可直接照抄）](#怎么调可直接照抄)
- [调用纪律](#调用纪律)
- [如果环境自带 SearXNG](#如果环境自带-searxng)
- [做不到的事](#做不到的事)

## 先判：是没网，还是没工具

发起一次最小试探后，按结果分三种：

| 现象 | 判定 | 去哪处理 |
| --- | --- | --- |
| 搜索工具存在但报配置错误（如缺 API key） | **没工具**，但可能有网 | 本文件 |
| 搜索工具不存在，但能抓网页 | 没工具 | 本文件 |
| 抓网页也失败（超时、DNS 失败） | 真离线 | `offline-degradation.md` |

判据只有一条：**能不能访问任意一个外部 URL**。能访问就有救。

典型报错形态：

```text
DeepSeek search has no API key for "DEEPSEEK_API_KEY"
```

这不是网络问题。此时不要直接宣布「无法检索」，按下面的顺序试公开端点，并守住三个端点的上限。

> **反例（2026-10-30 实测）**：搜索工具报 `no API key`，改打 DuckDuckGo 与 Brave 两个端点，都是 `fetch failed`（连不上）；同一台机器的 shell 也起不来（`0xC0000142`）。这种情况三个端点都救不回来，属于「工具有、网没通」，按 `offline-degradation.md` 带记录降级。**当时只试了两个端点就降级，看起来像没尽力**——差的就是《离线降级》第二节第五句那份检索记录。

## 调用顺序与上限

兜底也要有收口，否则「没工具」会变成无限换端点。

| 顺序 | 端点 | 什么时候用 |
| --- | --- | --- |
| 1 | DuckDuckGo HTML | 默认首选 |
| 2 | Brave | DuckDuckGo 判为不可用（202 挑战页、无关键词、连不上） |
| 3 | 下表其它标记为可用的端点 | 前两个都不可用 |
| — | SearXNG（若环境提供） | 环境变量存在且可用时，**排在第 1 位**，不占下面 3 个的名额 |

**上限 3 个公开端点，每个端点只试一条查询。** 三个都失败，说明这台机器的出站访问有问题，不是端点的问题——立即转 `offline-degradation.md`，并把试过的端点与报错写进降级提示的第五句。

这条上限的理由和第 1 节是同一条：**兜底不是重试，是换路。** 同一条路换三个引擎打六遍，拿回来的还是同一份「没有网」。

## 实测可用的公开端点

以下全部在 2026-10-29 实测，Windows + PowerShell 环境，无需 API key。

| 端点 | URL 形态 | 状态 | 相关度 |
| --- | --- | --- | --- |
| **DuckDuckGo HTML** | `https://html.duckduckgo.com/html/?q={query}` | 200，约 2.1s | **高**，推荐首选 |
| **Brave** | `https://search.brave.com/search?q={query}` | 200，约 3.5s | **高**，结果量大但页面重 |
| Bing | `https://www.bing.com/search?q={query}` | 200，约 1.3s | **不可用**，见下 |
| Mojeek | `https://www.mojeek.com/search?q={query}` | 403 | 不可用 |
| Startpage | `https://www.startpage.com/sp/search?query={query}` | 200，但无结果结构 | 不可用 |
| SearXNG（若环境提供） | 地址从 `OPENCLAW_WEB_SEARCH_SEARXNG_BASE_URL` 读 | 视环境而定 | 有则优先，不要假设存在 |

## 端点的实测结论

**Bing 不能用于中文查询。** 实测查询「赣州 奶茶店 店员 工资」，返回的 10 个 `b_algo` 结果块全是无关广告（男鞋、彩票），页面里「赣州」只出现 6 次，「奶茶」6 次。加 cookie 会话重试后依然如此。

**结论：Bing 对非浏览器请求返回广告填充页，不能作为检索来源。** 不要因为它 HTTP 200 就认为可用——必须检查返回内容是否含查询关键词。

**DuckDuckGo 与 Brave 返回真实结果。** 同一查询，Brave 页面里「奶茶」出现 105 次、「赣州」37 次，是真实结果页。

**DuckDuckGo 有反爬。** 只带 User-Agent 的 Python `urllib` 请求拿到 **HTTP 202 + 约 14 KB 挑战页**（零结果）；补上完整 Accept / Accept-Language / Referer 头并加 Cookie 处理器后，变成 **HTTP 200 + 31 KB + 10 条结果**。PowerShell 的 `Invoke-WebRequest` 默认头更全，所以一开始就能拿到结果。

**共同要求**：必须带浏览器 User-Agent，且 DuckDuckGo 还要完整的 Accept 系列头与 Cookie 处理。缺一项就可能拿到 202 空页。

## 怎么调（可直接照抄）

### DuckDuckGo（推荐首选）

```bash
curl -s -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" \
  "https://html.duckduckgo.com/html/?q=%E8%B5%A3%E5%B7%9E%20%E6%9C%80%E4%BD%8E%E5%B7%A5%E8%B5%84"
```

结果解析：按 `result__a`（标题）与 `result__snippet`（摘要）成对提取。

**Python 版必须带完整请求头 + Cookie 处理器**，只带 User-Agent 会拿到 HTTP 202 反爬挑战页（约 14 KB，零结果）：

```python
import re, urllib.parse, urllib.request, http.cookiejar

def ddg(query, n=8):
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/131.0.0.0 Safari/537.36"),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "identity",
        "Referer": "https://html.duckduckgo.com/",
    }
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    resp = opener.open(urllib.request.Request(url, headers=headers), timeout=25)
    html = resp.read().decode("utf-8", "replace")
    pat = re.compile(r'result__a[^>]*>(.*?)</a>.*?result__snippet[^>]*>(.*?)</a>',
                     re.S)
    strip = lambda s: re.sub(r"<[^>]+>", "", s).strip()
    return [(strip(t), strip(s)) for t, s in pat.findall(html)][:n]
```

这段代码在 2026-10-29 实测：HTTP 200，解析出 10 条真实结果。**只去掉 Cookie 处理器或 Accept 头就会退回 202 挑战页**，这点务必保留。

### Brave

```bash
curl -s -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
(KHTML, like Gecko) Chrome/131.0 Safari/537.36" \
  "https://search.brave.com/search?q=%E8%B5%A3%E5%B7%9E%20%E8%8C%B6%E9%A5%AE%20%E5%B7%A5%E8%B5%84"
```

页面较重（约 170 KB），且结构随版本变化，用于交叉验证，不做主渠道。

### PowerShell 版（Windows 环境）

```powershell
$enc = [uri]::EscapeDataString('赣州 最低工资标准')
$r = Invoke-WebRequest "https://html.duckduckgo.com/html/?q=$enc" -TimeoutSec 20 `
      -UseBasicParsing -Headers @{'User-Agent'='Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
[regex]::Matches($r.Content, 'result__a[^>]*>(.*?)</a>.*?result__snippet[^>]*>(.*?)</a>', 'Singleline') |
  ForEach-Object {
    ($_.Groups[1].Value -replace '<[^>]+>','' -replace '\s+',' ').Trim()
    ($_.Groups[2].Value -replace '<[^>]+>','' -replace '\s+',' ').Trim()
  }
```

## 调用纪律

这仍然是检索，**一样受 `runtime-loop.md` 的预算约束**（线上必查项 × 2，上限 12；成本类单独 2 个）。换端点不等于可以多搜。

四条额外要求：

1. **必须验证结果相关。** 拿到 HTML 不算成功，要检查返回内容里有没有查询主体的关键词。Bing 的教训就在这里：HTTP 200 但内容是广告。
2. **带浏览器 User-Agent。** 裸 `urllib` 默认 UA 常被拒。
3. **一次只用一个端点，失败再换。** 不要三个端点同时打同样的查询，那是三倍预算换同一份信息。
4. **端点结果只当线索。** 摘要用来发现线索，原文用来做依据（`research-protocol.md`）。政策条款必须再打开原文。

## 如果环境自带 SearXNG

有些环境会配 SearXNG 作为搜索后端。**不要假设它存在**——先查环境里有没有这两项变量，有的话再测端口通不通：

```text
OPENCLAW_WEB_SEARCH_PROVIDER=searxng
OPENCLAW_WEB_SEARCH_SEARXNG_BASE_URL=<地址>
```

三种结果，处理不同：

| 情况 | 处理 |
| --- | --- |
| 变量不存在 | **正常情况**，直接用上面的公开端点，不要去找 SearXNG |
| 变量在但端口连不上 | 服务没启动。**不要等它，也不要尝试启动它**，直接用公开端点 |
| 变量在且可用 | 优先用它，因为它是为这个环境配好的 |

**不要在本文件里记录某个具体环境的地址。** 别人的机器上没有那个服务，写进来只会让人白试一次。地址一律从环境变量读，读不到就走公开端点。

## 做不到的事

公开端点能搜到，但**打开原文可能失败**：

- 招聘平台（BOSS 直聘、智联、58 同城）多为 JS 渲染或反爬，摘要能拿到，薪资详情页常打不开
- 政策原文页一般能打开，优先用政府域名
- 商铺租金的挂牌信息可拿到区间，但成交价拿不到

遇到打不开原文的，按 `offline-degradation.md` 的「半离线」处理：**政策类按「没查到」算，不能用摘要当依据**。

这一点尤其重要：招聘摘要里写「3-6K」可以当区间线索，但不能当「当地实发工资」写进 H2 的分母。
