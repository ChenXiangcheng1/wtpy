from wtpy.apps.datahelper import DHFactory as DHF
from wtpy.apps.datahelper.DHTushare import DHTushare

hlper_DHTushare = DHF.createHelper('tushare')

# 认证
hlper_DHTushare.auth(**{'token': 'your token of tushare', 'use_pro': True})

# 将代码列表下载到文件中
hlper_DHTushare.dmpCodeListToFile(filename='codes.json', hasStock=True, hasIndex=True)

# 将除权因子下载到文件中
hlper_DHTushare.dmpAdjFactorsToFile(codes=['SSE.600000', 'SZSE.000001'], filename='./adjfactors.json')

# 将K线下载到指定目录
hlper_DHTushare.dmpBarsToFile('./', codes=['SSE.600000', 'SZSE.000001'], period='day')
