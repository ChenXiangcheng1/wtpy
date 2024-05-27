# from Strategies.RBreaker import StraRBreaker
from demos.Strategies.RBreaker import StraRBreaker
from wtpy import EngineType, WtBtEngine
from wtpy.apps import WtBtAnalyst

if __name__ == "__main__":
    #创建一个运行环境，并加入策略
    engine = WtBtEngine(EngineType.ET_CTA)
    engine.init('../common/', "configbt.yaml")
    engine.configBacktest(201909100930,201912011500)
    engine.configBTStorage(mode="csv", path="../storage/")
    engine.commitBTConfig()

    straInfo = StraRBreaker(name='pyrb_IF', code="CFFEX.IF.HOT", barCnt=50, period="m5", N=30, a=0.35, b=1.07, c = 0.07, d=0.25, cleartimes=[[1455,1515]])
    engine.set_cta_strategy(straInfo)

    engine.run_backtest()

    analyst = WtBtAnalyst()
    analyst.add_strategy("pyrb_IF", folder="./outputs_bt/pyrb_IF/", init_capital=500000, rf=0.02, annual_trading_days=240)
    analyst.run_new()

    kw = input('press any key to exit\n')
    engine.release_backtest()
