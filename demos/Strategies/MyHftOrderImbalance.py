from datetime import datetime

from wtpy import BaseHftStrategy, HftContext
from wtpy.ProductMgr import ProductInfo
from wtpy.WtDataDefs import WtNpTicks


def makeTime(date:int, time:int, secs:int):
    '''
    将系统时间转成datetime\n
    @date   日期，格式如20200723\n
    @time   时间，精确到分，格式如0935\n
    @secs   秒数，精确到毫秒，格式如37500
    '''
    return datetime(year=int(date/10000), month=int(date%10000/100), day=date%100,
        hour=int(time/100), minute=time%100, second=int(secs/1000), microsecond=secs%1000*1000)


# Reference: https://zhuanlan.zhihu.com/p/349167970
class HftOrderImbalance(BaseHftStrategy):
    def __init__(
        self,
        name: str,
        code: str,
        expsecs: int,
        stoppl: dict,
        freq: int = 30,
        lots: int = 1,
        count: int = 100,
        beta_0: float = 0.0,
        beta_r: float = 0.0,
        threshold: float = 0.0,
        beta_oi: list = [0.0, 0.0, 0.0],
        beta_rou: list = [0.0, 0.0, 0.0],
        active_secs: list = [0, 0],
    ):
        """
            @stoppl dict,止盈止损配置：止损跳数、追踪阈值、回撤边界
        """
        super().__init__(name)

        """交易参数"""
        self.__code__ = code  # 交易合约code
        self.__expsecs__ = expsecs  # 订单超时秒数，用于控制超时撤单
        self.__freq__ = freq  # 交易频率控制，指定时间内限制信号数，单位秒


        self.count = count  # 回溯tick条数

        self.beta_rou = beta_rou  # 委比因子系数序列
        self.threshold = threshold  # 中间价变动阈值
        self.beta_0 = beta_0  # 常量系数+残差
        self.beta_r = beta_r  # 中间价回归因子系数
        self.beta_oi = beta_oi  # 成交量不平衡因子系数序列

        self.__lots__ = lots  # 单次交易手数

        self.stoppl = stoppl  # 止盈止损配置

        self.active_secs = active_secs  # 交易时间区间


        '''内部数据'''
        # self.__comm_info__ = None
        self.__comm_info__ = ProductInfo()  # 品种信息ProductInfo对象
        self.__orders__ = dict()  #策略相关的订单

        self.__cancel_cnt__ = 0  #正在撤销的订单数,用于超时撤单 收盘撤单

        self._last_entry_price = 0.0  # 上次成交价，用于计算浮动盈亏
        self._max_dyn_prof = 0.0
        self._max_dyn_loss = 0.0

    def on_init(self, context: HftContext):
        # Initialize the strategy
        self.__comm_info__: ProductInfo = context.stra_get_comminfo(self.__code__)  # 获取品种信息
        context.stra_sub_ticks(self.__code__)  # #订阅实时tick数据
        self.__ctx__ = context

    def get_price(self, newTick, pricemode: int=0):
        """
            根据pricemode获取价格，0为当前价，1为卖一价，-1为买一价
        """
        if pricemode == 0:
            return newTick["price"]
        elif pricemode == 1:  # 卖一价
            return newTick["askprice"][0] if len(newTick["askprice"])>0 else newTick["price"]
        elif pricemode == -1:  # 买一价
            return newTick["bidprice"][0] if len(newTick["bidprice"])>0 else newTick["price"]

    def check_orders(self, ctx:HftContext):
        """
            检查未完成订单，如果超时则撤单
        """
        ord_cnt = len(self.__orders__.keys())
        if ord_cnt > 0 and self.__last_entry_time__ is not None:  #如果未完成订单不为空
            #当前时间，一定要从api获取，不然回测会有问题
            now = makeTime(ctx.stra_get_date(), ctx.stra_get_time(), ctx.stra_get_secs())
            span = now - self.__last_entry_time__
            total_secs = span.total_seconds()
            if total_secs >= self.__expsecs__: #如果订单超时，则需要撤单
                ctx.stra_log_text("%d条订单超时撤单" % (ord_cnt))
                for localid in self.__orders__:
                    ctx.stra_cancel(localid)
                    self.__cancel_cnt__ += 1
                    ctx.stra_log_text("在途撤单数 -> %d" % (self.__cancel_cnt__))


    def is_active(self, curMin:int) -> bool:
        """判断是否在交易时间内"""
        for sec in self.active_secs:
            if sec["start"] <= curMin and curMin <= sec["end"]:
                return True
        return False


    def on_tick(self, context: HftContext, stdCode: str, newTick: dict):
        # Handle tick data
        """
            基于self.count笔tick数据中的委托量的不平衡因子、委比因子以及中间价回归因子三个因子，
            预测t0时刻之后的k笔tick数据的中间价的均价变化量，并以此构建线性模型。
            通过线性回归，得到各个因子的系数。

            newTick: dict结构看WTSTickStruct
        """

        now = makeTime(self.__ctx__.stra_get_date(), self.__ctx__.stra_get_time(), self.__ctx__.stra_get_secs())

        #如果有未完成订单，则进入订单管理逻辑
        if len(self.__orders__.keys()) != 0:
            self.check_orders(context)
            return

        """ 收盘前出场的逻辑 """
        curMin = context.stra_get_time()  # 获取当前时间(时分)
        curPos = context.stra_get_position(stdCode)  # 获取当前持仓

        # 不在交易时间，则检查是否有持仓
        # 如果有持仓，则需要清理
        if not self.is_active(curMin):  # 不在交易时间内，则清理持仓
            self._last_atp__ = 0.0
            if curPos == 0:
                return
            self.__to_clear__ = True
        else:
            self.__to_clear__ = False

        # 如果需要清理持仓，且不在撤单过程中
        if self.__to_clear__ :  # 清理持仓
            if self.__cancel_cnt__ == 0:
                if curPos > 0:  # 如果是多头持仓
                    # 以对手价挂单
                    targetPx = self.get_price(newTick, -1)
                    assert targetPx is not None
                    ids = context.stra_sell(self.__code__, targetPx, abs(curPos), "deadline")

                    #将订单号加入到管理中
                    for localid in ids:
                        self.__orders__[localid] = localid
                elif curPos < 0:  # 如果是空头持仓
                    # 以对手价挂单
                    targetPx = self.get_price(newTick, 1)
                    assert targetPx is not None
                    ids = context.stra_buy(self.__code__, targetPx, abs(curPos), "deadline")

                    #将订单号加入到管理中
                    for localid in ids:
                        self.__orders__[localid] = localid

            return


        """止盈止损逻辑"""
        if curPos != 0 and self.stoppl["active"]:
            isLong = (curPos > 0)

            # 首先获取最新的价格
            price = 0
            if self.stoppl["calc_price"] == 0:  # calc_price为0的话，使用对手价计算浮盈
                # 逻辑：如果是多头持仓，使用卖一价计算浮盈；如果是空头持仓，使用买一价计算浮盈
                price = self.get_price(newTick, -1) if isLong else self.get_price(newTick, 1)
            else:  # calc_price为1的话，使用最新价计算浮盈
                price = newTick["price"]
            #然后计算浮动盈亏的跳数
            assert price is not None
            # 计算浮动盈亏的跳数=（当前价格-上次成交价）*（1或-1）/最小跳动价
            diffTicks = (price - self._last_entry_price) * (1 if isLong else -1) / self.__comm_info__.pricetick
            if diffTicks > 0:
                # 计算最大浮盈=最大浮盈和当前浮盈的最大值
                self._max_dyn_prof = max(self._max_dyn_prof, diffTicks)
            else:
                # 计算最大浮亏=最大浮亏和当前浮亏的最大值
                self._max_dyn_loss = min(self._max_dyn_loss, diffTicks)

            bNeedExit = False  # 是否需要离场
            usertag = ''  # 离场原因
            stop_ticks = self.stoppl["stop_ticks"]  # 止损跳数
            track_threshold = self.stoppl["track_threshold"]  # 追踪阈值
            fallback_boundary = self.stoppl["fallback_boundary"]  # 回撤边界
            if diffTicks <= stop_ticks:  # 如果跳数小于等于止损跳数，需要止损离场
                context.stra_log_text("浮亏%.0f超过%d跳，止损离场" % (diffTicks, stop_ticks))
                bNeedExit = True
                usertag = "stoploss"
            elif self._max_dyn_prof >= track_threshold and diffTicks <= fallback_boundary:  # 如果浮盈超过了追踪阈值，且浮亏未超过回撤边界，需要止盈离场
                context.stra_log_text(f"浮赢回撤{self._max_dyn_prof:.0f}->{diffTicks:.0f}[阈值{track_threshold:.0f}->{fallback_boundary:.0f}]，止盈离场")
                bNeedExit = True
                usertag = "stopprof"

            if bNeedExit:
                targetprice = self.get_price(newTick, -1) if isLong else self.get_price(newTick, 1)
                assert targetprice is not None
                ids = context.stra_sell(self.__code__, targetprice, abs(curPos), usertag) if isLong else context.stra_buy(self.__code__, price, abs(curPos), usertag)
                for localid in ids:
                    self.__orders__[localid] = localid

                # 出场逻辑执行以后结束逻辑
                return


        """ 进出场逻辑 """
        hisTicks: WtNpTicks = context.stra_get_ticks(self.__code__, self.count + 1)
        if len(hisTicks) != self.count+1:
            return

        if (len(newTick["askprice"]) == 0) or (len(newTick["bidprice"]) == 0):
            return

        spread = newTick["askprice"][0] - newTick["bidprice"][0]  # 当前价差：卖0-买0

        total_OIR = 0.0  # 不平衡因子累加之和
        total_rou = 0.0  # 委比因子累加之和

        # 计算不平衡因子和委比因子的累加之和
        for i in range(1, self.count + 1):
            # prevTick = hisTicks.get_tick(i-1)
            # curTick = hisTicks.get_tick(i)
            # 这里可能有问题
            prevTick = hisTicks[i-1]
            curTick = hisTicks[i]

            lastBidPx = self.get_price(prevTick, -1)  # 上一tick的买一价
            lastAskPx = self.get_price(prevTick, 1)  # 上一tick的卖一价

            lastBidQty = prevTick["bidqty"][0] if len(prevTick["bidqty"]) > 0 else 0  # 买一量
            lastAskQty = prevTick["askqty"][0] if len(prevTick["askqty"]) > 0 else 0  # 卖一量

            curBidPx = self.get_price(curTick, -1)  # 当前tick的买一价
            curAskPx = self.get_price(curTick, 1)  # 当前tick的卖一价

            curBidQty = curTick["bidqty"][0] if len(curTick["bidqty"]) > 0 else 0
            curAskQty = curTick["askqty"][0] if len(curTick["askqty"]) > 0 else 0

            # 核心逻辑1：计算不平衡因子
            delta_vb = 0.0
            delta_va = 0.0
            assert curBidPx is not None
            if curBidPx < lastBidPx:  # 逻辑：如果当前买一价小于上一次买一价，说明买一价下降，不平衡因子为0; 否则为当前买一量 ；或当前买一量-上一次买一量
                delta_vb = 0.0
            elif curBidPx == lastBidPx:
                delta_vb = curBidQty - lastBidQty
            else:
                delta_vb = curBidQty

            assert curAskPx is not None
            if curAskPx < lastAskPx:  # 逻辑：如果当前卖一价小于上一次卖一价，说明卖一价下降，不平衡因子为当前卖一量；否则为0；或当前卖一量-上一次卖一量
                delta_va = curAskQty
            elif curAskPx == lastAskPx:
                delta_va = curAskQty - lastAskQty
            else:
                delta_va = 0.0
            voi = delta_vb - delta_va
            # 总不平衡因子公式：累加所有tick的不平衡因子
            total_OIR += self.beta_oi[i-1]*voi/spread

            # 核心逻辑2：计算委比因子
            # 委比因子公式：(当前买一量-当前卖一量)/(当前买一量+当前卖一量)
            rou = (curBidQty - curAskQty)/(curBidQty + curAskQty)
            # 总委比因子公式：累加所有tick的委比因子
            total_rou += self.beta_rou[i-1]*rou/spread


        # prevTick = hisTicks.get_tick(-2)
        prevTick = hisTicks[-2]
        # t-1时刻的中间价
        t = self.get_price(prevTick, -1)
        assert t is not None
        prevMP = (t + self.get_price(prevTick, 1))/2
        # 最新的中间价
        curMP = (newTick["askprice"][0] + newTick["bidprice"][0])/2
        # 两个快照之间的成交均价
        if newTick["volumn"] != 0:
            avgTrdPx = newTick["turn_over"]/newTick["volumn"]/self.__comm_info__.volscale
        elif self._last_atp__!= 0:
            avgTrdPx = self._last_atp__
        else:
            avgTrdPx = curMP

        self._last_atp__ = avgTrdPx

        # 计算中间价回归因子
        curR = avgTrdPx - (prevMP + curMP) / 2

        # 计算预期中间价变化量
        # efpc = 常量系数 + 不平衡因子 + 委比因子 + 中间价回归因子
        efpc = self.beta_0 + total_OIR + total_rou + self.beta_r * curR / spread


        if efpc >= self.threshold:  # 买！！！
            targetPos = self.__lots__
            diffPos = targetPos - curPos
            if diffPos != 0.0:
                targetPx = newTick["askprice"][0]
                ids = context.stra_buy(self.__code__, targetPx, abs(diffPos), "enterlong")

                #将订单号加入到管理中
                for localid in ids:
                    self.__orders__[localid] = localid
                self.__last_entry_time__ = now  # 记录最后一次交易时间
                self._max_dyn_prof = 0  # 重置最大浮盈
                self._max_dyn_loss = 0  # 重置最大浮亏
        elif efpc <= -self.threshold:  # 卖！！！
            targetPos = -self.__lots__
            diffPos = targetPos - curPos
            if diffPos != 0:
                targetPx = newTick["bidprice"][0]
                ids = context.stra_sell(self.__code__, targetPx, abs(diffPos), "entershort")

                #将订单号加入到管理中
                for localid in ids:
                    self.__orders__[localid] = localid
                self.__last_entry_time__ = now
                self._max_dyn_prof = 0.0
                self._max_dyn_loss = 0.0

    def on_bar(self, context: HftContext):
        # Handle bar data
        pass

    def on_order_new(self, context: HftContext):
        # Handle new order event
        pass

    def on_order_fill(self, context: HftContext):
        # Handle order fill event
        pass

    def on_order_cancel(self, context: HftContext):
        # Handle order cancel event
        pass

    def on_order_reject(self, context: HftContext):
        # Handle order reject event
        pass

    def on_order_timeout(self, context: HftContext):
        # Handle order timeout event
        pass

    def on_order_finish(self, context: HftContext):
        # Handle order finish event
        pass

    def on_task(self, context: HftContext):
        # Handle task event
        pass

    def on_exit(self, context: HftContext):
        # Handle exit event
        pass

    def on_channel_ready(self, context: HftContext):
        # Handle channel ready event
        undone = context.stra_get_undone(self.__code__)  # 获取未完成订单
        if undone != 0 and len(self.__orders__.keys()) == 0:
            context.stra_log_text(f"{self.__code__}存在不在管理中的未完成单{undone:f}手，全部撤销")
            isBuy = (undone > 0)
            ids = context.stra_cancel_all(self.__code__, isBuy)  # 撤销所有未完成订单
            for localid in ids:
                self.__orders__[localid] = localid
            self.__cancel_cnt__ += len(ids)
            context.stra_log_text("在途撤单数 -> %d" % (self.__cancel_cnt__))
        self.__channel_ready__ = True

    def on_channel_lost(self, context: HftContext):
        # Handle channel lost event
        context.stra_log_text("交易通道连接丢失")
        self.__channel_ready__ = False

    # def on_entrust(self, context: HftContext, localid: int, stdCode: str, bSucc: bool, msg: str, userTag: str):
    #     # Handle entrust event
    #     if localid in self.__orders__:
    #         del self.__orders__[localid]
    #         if not bSucc:
    #             self.__cancel_cnt__ -= 1

    def on_order(self, context: HftContext, localid: int, stdCode: str, isBuy: bool, totalQty: float, leftQty: float, price: float, isCanceled: bool, userTag: str):
        # Handle order event
        if isCanceled or leftQty == 0:  # 如果订单已经撤单或者已经全部成交，则删除订单
            self.__orders__.pop(localid)
            if self.__cancel_cnt__ > 0:
                self.__cancel_cnt__ -= 1  # 撤单数减一
                self.__ctx__.stra_log_text("在途撤单数 -> %d" % (self.__cancel_cnt__))
        return

    def on_trade(self, context:HftContext, localid:int, stdCode:str, isBuy:bool, qty:float, price:float, userTag:str):
        self._last_entry_price = price  # 记录最后一次成交价
