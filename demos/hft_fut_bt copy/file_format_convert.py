import os

from wtpy.wrapper import WtDataHelper

dtHelper = WtDataHelper()
# dtHelper.dump_ticks('C:/Users/pc336/Desktop/CFFEX.IF.HOT_ticks_20201201_20210118', 'C:/Users/pc336/Desktop/hft_fut_bt_csvdata_2/')
dtHelper.dump_ticks('./in', './out2/')
# print(1)
# dtHelper.dump_ticks('/mnt/C/Users/pc336/Desktop/in', '/mnt/C/Users/pc336/Desktop/out2/')
print("succeed!")
