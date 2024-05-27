# 0513始


随便记记，写的有点乱


# 1流计算

DDB：

输入：插入流数据表

计算：订阅流数据表handler处理



Clickhouse

计算：Flink提供滚动窗口、滑动窗口、会话窗口



|            | 释义(侧重于)                                                 | 解决                                   |
| ---------- | ------------------------------------------------------------ | -------------------------------------- |
| 实时数据库 | 对用户随机发起的查询进行**低延迟响应**                       | 数据分片、向量化处理、预聚合、构建索引 |
| 流处理引擎 | 实时ETL(实时接收数据)<br />**实时处理数据流**，并将处理结果导入下游的存储系统供用户访问 |                                        |

如果有用流计算生成实时高频因子的需求，技术选型应该是：流处理引擎+实时数据库

流处理引擎实现的功能：窗口运算、[一致性-精确一次性（exactly once）](https://juejin.cn/post/6969124243275513887#heading-2)、[乱序处理（out-of-order processing）](https://blog.csdn.net/datacreating/article/details/129494944)



## DDB

createTimeSeriesEngine() [创建流数据聚合引擎]()



[如何将写入流数据表]()

streamTable() 流数据表



[通过]()subscribeTable()方法订阅流数据表level2，实现从API读取数据

[handler]()参数：用于处理订阅的数据，可以将数据注入流数据聚合引擎进行计算 或者 UDF 处理



https://docs.dolphindb.cn/zh/help/FunctionsandCommands/FunctionReferences/s/subscribeTable.html



缺点：2w/1cpu





## Clickhouse

流式插入引擎

* 物化视图：预查询快照

* 视图是虚拟表，本身不存储数据



## [Apache Flink](https://flink.apache.org/zh/)

> Apache Flink 是一个框架和分布式处理引擎，用于在*无边界和有边界*数据流上进行有状态的计算。

Flick 中的窗口：

- 时间窗口（Time Window）

1. 滚动时间窗口
2. 滑动时间窗口(滚动窗口+滑动间隔)
3. 会话窗口(一段时间内没有接收到新数据就会生成新的窗口)

- 计数窗口 （Count Window）

1. 滚动计数窗口
2. 滑动计数窗口





## 数据存储格式

Arrow 内存数据交换格式，作为统一的中间格式，

Rarquet 列式

在异构大数据系统中，如果全链路使用 Arrow 格式作为统一的中间格式，能够极大降低在不同系统之间传输数据的开销。

DolphinDB 开发了能够将 DolphinDB 数据格式和 Arrow 数据格式相互转换的数据格式插件。在高频使用 Apache Arrow 格式作为中间格式的场景，DolphinDB Arrow 插件能够帮助用户方便地从数据库取出数据、进而在不同系统（Spark 等）和应用程序间低成本、高效地传递数据。

数据仓库：湖仓一体lackhouse = 数据仓库 + 数据湖
评价：不成熟





# 2Order Book

## 资料

[上交所业务文档](https://www.sseinfo.com/services/assortment/document/)	|	[深交所数据接口](https://www.szse.cn/marketServices/technicalservice/interface/)

[上交所LDDS level2行情接口说明书20131016](https://www.sseinfo.com/services/assortment/document/interface/c/10747483/files/a4de433d5dda438c9cafd7fa6ed15cde.pdf)	|	[深交所Binary行情数据接口规范](https://www.szse.cn/marketServices/technicalservice/interface/P020230913351492727127.pdf)



### 交易阶段

| 交易阶段                         | 释义                                         | 股票  |
| -------------------------------- | -------------------------------------------- | ----- |
| 开盘集合竞价-可撤单              |                                              | 9:15  |
| 开盘集合竞价-不可撤单            |                                              | 9:20  |
| 撮合成交时间-不接受买入/卖出申报 | 根据最大成交量撮合，开盘价为所有人的成交价格 | 9:25  |
| 连续竞价                         |                                              | 9:30  |
| 午休                             |                                              | 11:30 |
| 连续竞价                         |                                              | 13:00 |
| 收盘集合竞价-不可撤单            |                                              | 14:57 |

商品期货：9:00-10:15 10:30-11:30 13:30-15:00
金融期货：9:15-11:30 13:00-15:15 21:00-2:30



### 戳合机制

1限价单委托：
	集合竞价：价格优先后再时间优先
	连续竞价：与对方价格档从高到底的订单队列匹配，将剩余订单加入本方该价格档订单队列的末尾

2市价单委托：
	连续竞价：
		上交所发送市价委托有五种方式：[OrdType](http://www.sse.com.cn/services/tradingtech/data/c/IS122_TDGW_STEP_CV0.55_MTP_20230407.pdf): 1=市转撤，2=限价，3=市转限，4=本方最优，5=对手方最优
		深交所发送市价委托也有五种方式：对手方最优价格申报、本方最优价格申报、即时成交剩余撤销申报、最优五档即时成交剩余撤销申报、全额成交或撤销申报
		深交所接收逐笔委托只分市价、本方最优，无法区分对手方市价单种类，**只能根据逐笔成交来确认**
		因此收到市价委托时不能直接判断出撮合结果，需等待成交到来。



3创业板(先不做)
	基准价格：优先选取对手方一档价格、本方一档价格、最近成交价、前收盘价，作为基准价格
	价格笼子：[98%, 102%]
	机制：当委托超出笼子范围，缓存在主机不撮合，直到基准价格变化后在范围只中



4数据：	
逐笔委托
逐笔成交
上交所 逐笔合并数据 UA5803 (在同一个通道内发送新增委托订单Order和删除委托订单Order、产品状态订单、成交Trade)
快照行情 用于校验订单薄



5两市区别：
深交所的逐笔成交数据里包含有撤单数据，上交所的撤单数据在逐笔委托里

上交所level2逐笔委托的数量Balance：是剩余成交量，是减去了所有主动成交量以后,还剩下的未成交量

上交所逐笔委托与逐笔成交没有固定的到达先后次序关系，需要通过BizIndex判断 (新出了逐笔合并数据UA5803 解决该问题)

价格和数量精度不同



BTW: 感觉 OrderBook 维护麻烦，交易所机制变动将导致重构订单簿代码也需要调整



## [阅读代码 AXOrderBook](https://github.com/fpga2u/AXOrderBook/tree/main?tab=readme-ov-file)

OB流-交易阶段的判断与切换：
快照行情 TradingPhaseCode 交易阶段代码 (可能不及时，只触发该标的的阶段切换)
逐笔行情的时间戳 (触发全局的阶段切换)
上交所 产品状态订单



集合竞价期间 根据最大成交量原则撮合成交价
连续竞价期间 撮合流程：
	逐笔委托：限价、市价
	逐笔成交：成交、撤单
TODO：等看代码时再细看，[重建OB](https://github.com/fpga2u/AXOrderBook/blob/PxPrecision4/doc/ob_workflow.md#集合竞价重建流程)、[数据结构](https://github.com/fpga2u/AXOrderBook/blob/PxPrecision4/doc/reference.md)



---

**数据结构**：[上交所、深交所主要差异](https://github.com/fpga2u/AXOrderBook/blob/PxPrecision4/doc/msgTypes.md#上交所、深交所主要差异)
	价格档位：
		每个个股独立、均有两棵价格树(bid/ask各一棵)
		价格树节点对应订单队列

OrderBook(seid)
	pricelevel(买卖方向,Price,order队列)
		Order：市价单、限价单、本方最优单(买一、卖一，未成交数量)	



L2数据处理：C结构体，小端存储(网络大端、内存小端)
TODO： msgTypes.md#上交所 完成深交所之后再看



---

py

主动根据逐笔委托：模拟交易所撮合机制进行成交判断

被动根据逐笔成交：**	**，根据成交Trade 维护价格档、委托数量
深交所对应的逐笔委托在逐笔成交之前

缺点：比根据逐笔委托慢，集合竞价阶段不能重建OB，没有维护委托队列





库：
struct.pack(fmt,v1,v2,.....) 二进制编码
TODO: pytest、[logging常用](https://blog.csdn.net/qq_41648043/article/details/109464115)、[typing类型注解文档](https://docs.python.org/zh-cn/3/library/typing.html) [typing笔记](https://cloud.tencent.com/developer/article/2331538)



目录结构：
tool/test/: 测试，没什么好看的
tool/msg_util: 行情数据工具类，可读取本项目使用的L2历史文件
tool/log_util: 日志工具类
tool/test_util.py: 测试用的工具类
tool/axsbe_base：行情基础抽象类
tool/axsbe_exe：逐笔成交行情
tool/order：逐笔委托行情
tool/axsbe_snap_stock：快照行情
mu.py：管理多个AXOB、交易阶段管理



TODO: 看run_test_behave.py、test_axob.py、mu.py、axob.py



## 数据源

level2非展示行情(DataFeed)：[深交所收费标准](http://www.szsi.cn/cpfw/fwsq/hq/sfbz-2.htm)、[上交所收费标准](https://www.sseinfo.com/services/charge/pricelist/c/10010713/files/b67c181c850b4879a715f1e06881d667.pdf) [许可](https://bsp.sseinfo.com/business/?id=1644178582138449922)

L2行情>实时行情>快照行情+逐笔行情



## Python实现

重构订单簿

难度：异常处理，不要导致行情错误



### 数据结构

LimitOrderBook
	Limit 买价格档二叉树 + 最优买价格节点指针
		Order 委托链表
	Limit 卖价格档二叉树 + 最优卖价格节点指针
		Order 委托链表

Limit: 由各价格档节点组成

{订单号: Order} 和 {价格: Limit}



用树存放价格档信息(指针)

用数组存放价格档信息(指针)



### 遇到的问题

不知道如何判断限价单、市价单？
解决：找了半天发现是在深交所逐笔委托的 Extend Fields 字段中 = =

如何维护价格档？

要处理的东西很多
先处理深交所，再处理上交所
先看股票，先放着基金、可转债、期权、债券、逆回购



## DDB实现



# 3WonderTrader

WtStudio：基于WonderTrader的客户端工具

应用层：wtpy，WtBtWrapper 封装底层C模块
	交易引擎WtEngine：WtEngine、init、commitConfig、add_hft_strategy、run
		策略调用Context，CTA(同步策略)CtaContext、SEL异步策略SelContext、HFT高频策略HftContext、UFT低延时急速策略
	回测引擎WtBtEngine：WtBtEngine、init、configBacktest、configBTStorage、commitBTConfig、set_cta_strategy、run_backtest、release_backtest
		绩效分析模块WtBtAnalyst：WtBtAnalyst、add_strategy、run_new
	数据引擎WtDtEngine



策略参数传入结束以后，触发策略的`on_init`接口，订阅tick数据，回调触发`on_tick` 接口，`on_session_end` 收盘作业

**策略开发调试流程：**

1. 首先根据目标策略复制一个工程，如`WtCtaStraFact`，并将工程名改成自己需要的工程名`XXXStraFact`
2. 然后，修改工厂类的类名为自己需要的类名，如将`WtStraFact`改成`XXXStraFact`
3. 第三，派生一个策略类，如`StraXXXX`，并完成策略的实现
   	定义交易参数......
4. 第四，修改工厂类中的`enumStrategy`和`createStrateg`y接口，将预定的策略名称和策略类关联起来



[基础文件详解](https://wtdocs.readthedocs.io/zh/latest/docs/usage/common_files.html)



---

## 概念

柜台交易：场外交易

头寸：款项
多头：收款>支出



alphalens：用于多因子分析

pyfolio：量化图表



除权：股票股利分配后需要对股价进行除权
除权因子：指除权价格的比率



年化夏普率：每一单位风险的超额回报 = (投资组合的预期回报率 - 无风险利率) / 投资组合的年化标准差



**期货概念：**

CTP：上期所的期货的综合交易平台
期货：未来商品，分为商品期货与金融期货(合约)。TODO： https://finance.sina.com.cn/futuremarket/help/4.html
期货主力合约：交易活跃的合约 hots.json主力合约规则
期货品种：map_future.ini



---

使用htf/uft引擎实现套利策略引擎



## datakit_fut demo

datakit：用于数据的后续处理，**实时数据录制**，一般数据局域网UDP组播
WtDtEngine数据引擎封装了datakit

改改配置就能跑



## cta_fut_bt 回测demo

CTA(Commodity Trading Advisor)策略：用于期货
常见的有：DualThrust通道突破策略、R-Breaker、菲阿里四价、空中花园

滑点：下单交易点与真实交易点不同



## htf_fut 高频策略demo

了解WonderTrader的HFT引擎上如何开发策略的
HFT策略流程：策略参数传入结束以后，触发策略的`on_init`接口，**订阅tick数据**，回调触发`on_tick` 接口，`on_channel_ready` 维护状态-策略相关的订单，`on_order` 维护状态-撤单数，`on_session_end` 收盘作业



on_tick()回调，用最新的tick计算一个理论价格，参考理论价格生成交易信号。

$理论价格 = (卖0价*卖0量+买0价*买0量)/(卖0量+买0量)$

* 理论价格>逐笔最新价 & 仓位 < 0
  	买入
* 理论价格<逐笔最新价 & 仓位 > 0
  	卖出

发生交易后，维护状态：
```python
        self.__last_tick__ = None       #上一笔行情
        self.__orders__ = dict()        #策略相关的订单,
        self.__last_entry_time__ = None #上次入场时间
        self.__cancel_cnt__ = 0         #正在撤销的订单数
        self.__channel_ready__ = False  #通道是否就绪
```



## htf_fut_bt demo

**`commodities.json`中一定要有回测的品种**

**品种与合约须手动检查，与`runBT.py`对应**

问题：不知道configbt.yaml配置项hft0的作用，文档中也没看到
解决：可能这块配置没用，先略过

```yaml
hft0:
    error_rate: 30
    module: WzHftStraFact
    strategy:
        name: OrderImbalance
        params:
            active_sections:
            -   end: 1457
                start: 931
            beta_0: 0.01171
```



### TODO

TODO：深入看看 engine.run_backtest() 



## [wtpy HFT初探](https://zhuanlan.zhihu.com/p/349167970)

```python
# efpc = 常量系数 + 不平衡因子 + 委比因子 + 中间价回归因子
efpc = self.beta_0 + total_OIR + total_rou + self.beta_r * curR / spread
```

线性模型：





![img](https://pic4.zhimg.com/80/v2-135d60de6b4e1ae50f5912d62de268eb_720w.webp)



### 逻辑

1超时则撤单

2止盈止损逻辑：**止损跳数**(>浮动盈亏的跳数 止损离场)、**浮盈阈值**(<最大浮盈 止盈离场)、回撤边界
	浮动盈亏的跳数 =（当前价格-上次成交价）*（1或-1）/最小跳动价
	计算最大浮盈、计算最大浮亏

3收盘前出场的逻辑：不在交易时间内清理多头持仓、空头持仓

4进出场逻辑：
	1计算**委托量的不平衡因子、委比因子、中间价回归因子**，生成买卖信号
	2交易执行
	3维护与策略相关的订单

买卖信号逻辑总结下来这公式和阈值比大小：

![](https://img2.imgtp.com/2024/05/27/I5C9pqVG.png)

**不平衡因子：表示买委托数 - 卖委托数**。正**表示市场有买入压力**，负表示市场有卖出压力

**委比因子**：表示买委托数 / 总委托数

```python
delta_vb = 0.0
delta_va = 0.0
assert curBidPx is not None
if curBidPx < lastBidPx:  # 逻辑：如果当前买一价小于上一次买一价，说明买一价下降(没有买入压力)，不平衡因子为0; 否则为当前买一量 ；或当前买一量-上一次买一量
    delta_vb = 0.0
elif curBidPx == lastBidPx:
    delta_vb = curBidQty - lastBidQty	# 有买入压力
else:
    delta_vb = curBidQty  # 有买入压力

assert curAskPx is not None
if curAskPx < lastAskPx:  # 逻辑：如果当前卖一价小于上一次卖一价，说明卖一价下降(有卖出压力)，不平衡因子为当前卖一量；否则为0；或当前卖一量-上一次卖一量
    delta_va = curAskQty
elif curAskPx == lastAskPx:
    delta_va = curAskQty - lastAskQty
else:
    delta_va = 0.0
    
# 总不平衡因子公式：累加所有tick的不平衡因子
total_OIR += self.beta_oi[i-1]*voi/spread
```



**委比因子**：表示买委托数 / 总委托数

```python
rou = (curBidQty - curAskQty)/(curBidQty + curAskQty)  # 委比因子

total_rou += self.beta_rou[i-1] * rou / spread  # 总委比因子：累加所有tick的委比因子
# 委比因子系数序列 * (当前买卖委托差 / 总委托数) / 卖0买0差
```



**中间价回归因子**：









### tick数据结构

```python
stra_get_ticks() 返回 WtNpTicks(__tick_cache__[stdCode:str]=newTicks:WtNpTicks)，WtNpTicks 是对 np.ndarray 的封装
	WtNpTicks[idx] 返回 np.ndarray[idx]
看https://wtdocs.readthedocs.io/zh/latest/docs/apis/interfaces.html#id3
	WtNpTicks是Tick矩阵，DataFrame结构，字段包括ticktime,open,high,low,price，索引为时间
```

```
on_tick() 参数 newTick 是一个字典，去看 WTSTickStruct
```



### 问题

问题：跑 demo/hft/fut_bt_copy，回测缺文件，没办法回测

问题：跑实盘 demo/hft/fut_bt_copy，缺少 SIMNOW账号

问题：比如 stra_buy()

其中 idstr 不知道具体结构是什么样的，文档里也没有

```python
def stra_buy(self, stdCode:str, price:float, qty:float, userTag:str = "", flag:int = 0):
    '''
    买入指令
    @id         策略ID
    @stdCode    品种代码
    @price      买入价格, 0为市价
    @qty        买入数量
    @flag       下单标志, 0-normal, 1-fak, 2-fok
    '''
    idstr = self.__wrapper__.hft_buy(self.__id__, stdCode, price, qty, userTag, flag)
    if len(idstr) == 0:
        return list()

    ids = idstr.split(",")
    localids = list()
    for localid in ids:
        localids.append(int(localid))
    return localids
```



### TODO

TODO：深入看 HftContext 的几个接口 API

[交易数据接口](https://wtdocs.readthedocs.io/zh/latest/docs/apis/interfaces.html#id3)



### 总结

wtpy 的机制是在回调函数中调用 Context 接口，执行因子计算，再执行交易操作



# 4React库

JSX标签：JavaScript语法扩展



