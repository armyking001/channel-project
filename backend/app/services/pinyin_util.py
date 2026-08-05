"""简易汉字拼音首字母 + 全拼工具
不依赖第三方库，内置常用姓氏/名字汉字字典
- get_first_letter(ch): 返回单个汉字的拼音首字母（'zhang' 的 'z'）
- get_full_pinyin(ch): 返回单个汉字的全拼小写（'zhang'）
- 字典仅覆盖常见汉字（覆盖常见姓氏 100+ 个 + 常见名字用字 200+ 个）
- 字典未覆盖的汉字默认 fallback 为 'x'（用户可手动改）
"""
import time


# 常见姓氏（百家姓前 200）
_SURNAME_PINYIN = {
    '赵': 'zhao', '钱': 'qian', '孙': 'sun', '李': 'li', '周': 'zhou',
    '吴': 'wu', '郑': 'zheng', '王': 'wang', '冯': 'feng', '陈': 'chen',
    '褚': 'chu', '卫': 'wei', '蒋': 'jiang', '沈': 'shen', '韩': 'han',
    '杨': 'yang', '朱': 'zhu', '秦': 'qin', '尤': 'you', '许': 'xu',
    '何': 'he', '吕': 'lv', '施': 'shi', '张': 'zhang', '孔': 'kong',
    '曹': 'cao', '严': 'yan', '华': 'hua', '金': 'jin', '魏': 'wei',
    '陶': 'tao', '姜': 'jiang', '戚': 'qi', '谢': 'xie', '邹': 'zou',
    '喻': 'yu', '柏': 'bai', '水': 'shui', '窦': 'dou', '章': 'zhang',
    '云': 'yun', '苏': 'su', '潘': 'pan', '葛': 'ge', '奚': 'xi',
    '范': 'fan', '彭': 'peng', '郎': 'lang', '鲁': 'lu', '韦': 'wei',
    '昌': 'chang', '马': 'ma', '苗': 'miao', '凤': 'feng', '花': 'hua',
    '方': 'fang', '俞': 'yu', '任': 'ren', '袁': 'yuan', '柳': 'liu',
    '酆': 'feng', '鲍': 'bao', '史': 'shi', '唐': 'tang', '费': 'fei',
    '廉': 'lian', '岑': 'cen', '薛': 'xue', '雷': 'lei', '贺': 'he',
    '倪': 'ni', '汤': 'tang', '滕': 'teng', '殷': 'yin', '罗': 'luo',
    '毕': 'bi', '郝': 'hao', '邬': 'wu', '安': 'an', '常': 'chang',
    '乐': 'le', '于': 'yu', '时': 'shi', '傅': 'fu', '皮': 'pi',
    '卞': 'bian', '齐': 'qi', '康': 'kang', '伍': 'wu', '余': 'yu',
    '元': 'yuan', '卜': 'bu', '顾': 'gu', '孟': 'meng', '平': 'ping',
    '黄': 'huang', '和': 'he', '穆': 'mu', '萧': 'xiao', '尹': 'yin',
    '姚': 'yao', '邵': 'shao', '湛': 'zhan', '汪': 'wang', '祁': 'qi',
    '毛': 'mao', '禹': 'yu', '狄': 'di', '米': 'mi', '贝': 'bei',
    '明': 'ming', '臧': 'zang', '计': 'ji', '伏': 'fu', '成': 'cheng',
    '戴': 'dai', '谈': 'tan', '宋': 'song', '茅': 'mao', '庞': 'pang',
    '熊': 'xiong', '纪': 'ji', '舒': 'shu', '屈': 'qu', '项': 'xiang',
    '祝': 'zhu', '董': 'dong', '梁': 'liang', '杜': 'du', '阮': 'ruan',
    '蓝': 'lan', '闵': 'min', '席': 'xi', '季': 'ji', '麻': 'ma',
    '强': 'qiang', '贾': 'jia', '路': 'lu', '娄': 'lou', '危': 'wei',
    '江': 'jiang', '童': 'tong', '颜': 'yan', '郭': 'guo', '梅': 'mei',
    '盛': 'sheng', '林': 'lin', '刁': 'diao', '钟': 'zhong', '徐': 'xu',
    '邱': 'qiu', '骆': 'luo', '高': 'gao', '夏': 'xia', '蔡': 'cai',
    '田': 'tian', '樊': 'fan', '胡': 'hu', '凌': 'ling', '霍': 'huo',
    '虞': 'yu', '万': 'wan', '支': 'zhi', '柯': 'ke', '昝': 'zan',
    '管': 'guan', '卢': 'lu', '莫': 'mo', '经': 'jing', '房': 'fang',
    '裘': 'qiu', '缪': 'miao', '干': 'gan', '解': 'xie', '应': 'ying',
    '宗': 'zong', '丁': 'ding', '宣': 'xuan', '贲': 'ben', '邓': 'deng',
    '郁': 'yu', '单': 'shan', '杭': 'hang', '洪': 'hong', '包': 'bao',
    '诸': 'zhu', '左': 'zuo', '石': 'shi', '崔': 'cui', '吉': 'ji',
    '钮': 'niu', '龚': 'gong', '程': 'cheng', '嵇': 'ji', '邢': 'xing',
    '滑': 'hua', '裴': 'pei', '陆': 'lu', '荣': 'rong', '翁': 'weng',
    '荀': 'xun', '羊': 'yang', '於': 'yu', '惠': 'hui', '甄': 'zhen',
    '曲': 'qu', '家': 'jia', '封': 'feng', '芮': 'rui', '羿': 'yi',
    '储': 'chu', '靳': 'jin', '汲': 'ji', '邴': 'bing', '糜': 'mi',
    '松': 'song', '井': 'jing', '段': 'duan', '富': 'fu', '巫': 'wu',
    '乌': 'wu', '焦': 'jiao', '巴': 'ba', '弓': 'gong', '牧': 'mu',
    '隗': 'wei', '山': 'shan', '谷': 'gu', '车': 'che', '侯': 'hou',
    '宓': 'mi', '蓬': 'peng', '全': 'quan', '郗': 'xi', '班': 'ban',
    '仰': 'yang', '秋': 'qiu', '仲': 'zhong', '伊': 'yi', '宫': 'gong',
    '宁': 'ning', '仇': 'qiu', '栾': 'luan', '暴': 'bao', '甘': 'gan',
    '钭': 'tou', '厉': 'li', '戎': 'rong', '祖': 'zu', '武': 'wu',
    '符': 'fu', '刘': 'liu', '景': 'jing', '詹': 'zhan', '束': 'shu',
    '龙': 'long', '叶': 'ye', '幸': 'xing', '司': 'si', '韶': 'shao',
    '郜': 'gao', '黎': 'li', '蓟': 'ji', '薄': 'bo', '印': 'yin',
    '宿': 'su', '白': 'bai', '怀': 'huai', '蒲': 'pu', '邰': 'tai',
    '从': 'cong', '鄂': 'e', '索': 'suo', '咸': 'xian', '籍': 'ji',
    '赖': 'lai', '卓': 'zhuo', '蔺': 'lin', '屠': 'tu', '蒙': 'meng',
    '池': 'chi', '乔': 'qiao', '阴': 'yin', '鬱': 'yu', '胥': 'xu',
    '能': 'neng', '苍': 'cang', '双': 'shuang', '闻': 'wen', '莘': 'shen',
    '党': 'dang', '翟': 'zhai', '谭': 'tan', '贡': 'gong', '劳': 'lao',
    '逄': 'pang', '姬': 'ji', '申': 'shen', '扶': 'fu', '堵': 'du',
    '冉': 'ran', '宰': 'zai', '郦': 'li', '雍': 'yong', '却': 'que',
    '璩': 'qu', '桑': 'sang', '桂': 'gui', '濮': 'pu', '牛': 'niu',
    '寿': 'shou', '通': 'tong', '边': 'bian', '扈': 'hu', '燕': 'yan',
    '冀': 'ji', '郏': 'jia', '浦': 'pu', '尚': 'shang', '农': 'nong',
    '温': 'wen', '别': 'bie', '庄': 'zhuang', '晏': 'yan', '柴': 'chai',
    '瞿': 'qu', '阎': 'yan', '充': 'chong', '慕': 'mu', '连': 'lian',
    '茹': 'ru', '习': 'xi', '宦': 'huan', '艾': 'ai', '鱼': 'yu',
    '容': 'rong', '向': 'xiang', '古': 'gu', '易': 'yi', '慎': 'shen',
    '戈': 'ge', '廖': 'liao', '庚': 'geng', '终': 'zhong', '暨': 'ji',
    '居': 'ju', '衡': 'heng', '步': 'bu', '都': 'du', '耿': 'geng',
    '满': 'man', '弘': 'hong', '匡': 'kuang', '国': 'guo', '文': 'wen',
    '寇': 'kou', '广': 'guang', '禄': 'lu', '阙': 'que', '东': 'dong',
    '欧': 'ou', '殳': 'shu', '沃': 'wo', '利': 'li', '蔚': 'wei',
    '越': 'yue', '夔': 'kui', '隆': 'long', '师': 'shi', '巩': 'gong',
    '厍': 'she', '聂': 'nie', '晁': 'chao', '勾': 'gou', '敖': 'ao',
    '融': 'rong', '冷': 'leng', '訾': 'zi', '辛': 'xin', '阚': 'kan',
    '那': 'na', '简': 'jian', '饶': 'rao', '空': 'kong', '曾': 'zeng',
    '母': 'mu', '沙': 'sha', '乜': 'mie', '养': 'yang', '鞠': 'ju',
    '须': 'xu', '丰': 'feng', '巢': 'chao', '关': 'guan', '蒯': 'kuai',
    '相': 'xiang', '查': 'zha', '后': 'hou', '荆': 'jing', '红': 'hong',
    '游': 'you', '竺': 'zhu', '权': 'quan', '逯': 'lu', '盖': 'gai',
    '益': 'yi', '桓': 'huan', '公': 'gong', '万': 'wan', '俟': 'si',
    '司马': 'sima', '上官': 'shangguan', '欧阳': 'ouyang', '夏侯': 'xiahou',
    '诸葛': 'zhuge', '东方': 'dongfang', '赫连': 'helian', '皇甫': 'huangfu',
    '尉迟': 'yuchi', '公羊': 'gongyang', '澹台': 'dantai', '公冶': 'gongye',
    '宗政': 'zongzheng', '濮阳': 'puyang', '淳于': 'chunyu', '单于': 'chanyu',
    '太史': 'taishi', '申屠': 'shentu', '公孙': 'gongsun', '仲孙': 'zhongsun',
    '轩辕': 'xuanyuan', '令狐': 'linghu', '钟离': 'zhongli', '宇文': 'yuwen',
    '长孙': 'zhangsun', '慕容': 'murong', '鲜于': 'xianyu', '闾丘': 'luqiu',
    '司徒': 'situ', '司空': 'sikong', '亓官': 'qiguan', '司寇': 'sikou',
    '仉': 'zhang', '督': 'du', '子': 'zi', '车': 'che', '亓': 'qi',
    '法': 'fa', '汝': 'ru', '鄢': 'yan', '涂': 'tu', '钦': 'qin',
    '段干': 'duangan', '百里': 'baili', '东郭': 'dongguo', '南门': 'nanmen',
    '呼延': 'huyan', '归': 'gui', '海': 'hai', '羊舌': 'yangshe', '微生': 'weisheng',
    '岳': 'yue', '帅': 'shuai', '缑': 'gou', '亢': 'kang', '况': 'kuang',
    '后': 'hou', '有': 'you', '琴': 'qin', '梁丘': 'liangqiu', '左丘': 'zuoqiu',
    '东门': 'dongmen', '西门': 'ximen', '商': 'shang', '牟': 'mou', '佘': 'she',
    '佴': 'nai', '伯': 'bo', '赏': 'shang', '南宫': 'nangong', '墨': 'mo',
    '哈': 'ha', '谯': 'qiao', '笪': 'da', '年': 'nian', '爱': 'ai',
    '阳': 'yang', '佟': 'tong', '第五': 'diwu', '言': 'yan', '福': 'fu',
    '覃': 'qin', '朴': 'piao', '甫': 'fu', '寸': 'cun', '脱': 'tuo',
    '宦': 'huan', '淳于': 'chunyu', '梁': 'liang', '皇甫': 'huangfu',
}

# 常见名字用字（首字母 + 全拼）
_GIVEN_NAME_PINYIN = {
    # 单字名常用
    '伟': 'wei', '芳': 'fang', '娜': 'na', '敏': 'min', '静': 'jing',
    '丽': 'li', '强': 'qiang', '磊': 'lei', '军': 'jun', '洋': 'yang',
    '勇': 'yong', '艳': 'yan', '杰': 'jie', '娟': 'juan', '涛': 'tao',
    '明': 'ming', '超': 'chao', '霞': 'xia', '平': 'ping', '刚': 'gang',
    '桂英': 'guiying', '桂兰': 'guilan', '建华': 'jianhua', '建平': 'jianping',
    '建国': 'jianguo', '建军': 'jianjun', '建设': 'jianshe', '建辉': 'jianhui',
    '建辉': 'jianhui', '建明': 'jianming', '建强': 'jianqiang', '建伟': 'jianwei',
    '建新': 'jianxin', '建忠': 'jianzhong', '建中': 'jianzhong', '建华': 'jianhua',
    '晓东': 'xiaodong', '晓东': 'xiaodong', '晓东': 'xiaodong',
    '小': 'xiao', '大': 'da', '中': 'zhong', '国': 'guo', '华': 'hua',
    '建': 'jian', '文': 'wen', '武': 'wu', '志': 'zhi', '勇': 'yong',
    '云': 'yun', '风': 'feng', '雨': 'yu', '雪': 'xue', '雷': 'lei',
    '俊': 'jun', '峰': 'feng', '山': 'shan', '海': 'hai', '河': 'he',
    '林': 'lin', '森': 'sen', '树': 'shu', '花': 'hua', '草': 'cao',
    '青': 'qing', '红': 'hong', '白': 'bai', '黑': 'hei', '黄': 'huang',
    '天': 'tian', '地': 'di', '人': 'ren', '心': 'xin', '手': 'shou',
    '口': 'kou', '目': 'mu', '耳': 'er', '足': 'zu', '心': 'xin',
    '美': 'mei', '丑': 'chou', '善': 'shan', '恶': 'e',
    '爱': 'ai', '恨': 'hen', '喜': 'xi', '怒': 'nu', '哀': 'ai',
    '乐': 'le', '悲': 'bei', '思': 'si', '念': 'nian', '想': 'xiang',
    '梦': 'meng', '醒': 'xing', '睡': 'shui', '醉': 'zui', '醒': 'xing',
    '男': 'nan', '女': 'nv', '老': 'lao', '少': 'shao', '幼': 'you',
    '永': 'yong', '浩': 'hao', '强': 'qiang', '伟': 'wei', '杰': 'jie',
    '勇': 'yong', '丽': 'li', '静': 'jing', '敏': 'min', '燕': 'yan',
    '艳': 'yan', '娟': 'juan', '涛': 'tao', '明': 'ming', '超': 'chao',
    '霞': 'xia', '平': 'ping', '刚': 'gang', '涛': 'tao', '俊': 'jun',
    '峰': 'feng', '凯': 'kai', '亮': 'liang', '辉': 'hui', '健': 'jian',
    '雄': 'xiong', '豪': 'hao', '美': 'mei', '玲': 'ling', '慧': 'hui',
    '洁': 'jie', '雪': 'xue', '梅': 'mei', '兰': 'lan', '菊': 'ju',
    '莲': 'lian', '宇': 'yu', '波': 'bo', '德': 'de', '仁': 'ren',
    '义': 'yi', '礼': 'li', '智': 'zhi', '信': 'xin', '忠': 'zhong',
    '孝': 'xiao', '东': 'dong', '南': 'nan', '西': 'xi', '北': 'bei',
    '父': 'fu', '母': 'mu', '子': 'zi', '女': 'nv', '兄': 'xiong',
    '弟': 'di', '姐': 'jie', '妹': 'mei', '夫': 'fu', '妻': 'qi',
    '春': 'chun', '夏': 'xia', '秋': 'qiu', '冬': 'dong',
    '东': 'dong', '南': 'nan', '西': 'xi', '北': 'bei',
    '左': 'zuo', '右': 'you', '前': 'qian', '后': 'hou', '上': 'shang',
    '下': 'xia', '中': 'zhong', '内': 'nei', '外': 'wai', '里': 'li',
    '金': 'jin', '木': 'mu', '水': 'shui', '火': 'huo', '土': 'tu',
    '风': 'feng', '雨': 'yu', '雷': 'lei', '电': 'dian', '光': 'guang',
    '日': 'ri', '月': 'yue', '星': 'xing', '辰': 'chen', '云': 'yun',
    '俊': 'jun', '峰': 'feng', '杰': 'jie', '亮': 'liang', '辉': 'hui',
    '健': 'jian', '强': 'qiang', '伟': 'wei', '雄': 'xiong', '豪': 'hao',
    '俊': 'jun', '美': 'mei', '丽': 'li', '娟': 'juan', '芳': 'fang',
    '艳': 'yan', '红': 'hong', '霞': 'xia', '玲': 'ling', '慧': 'hui',
    '敏': 'min', '静': 'jing', '洁': 'jie', '雪': 'xue', '梅': 'mei',
    '兰': 'lan', '菊': 'ju', '莲': 'lian', '燕': 'yan', '燕': 'yan',
    '宇': 'yu', '宙': 'zhou', '洪': 'hong', '波': 'bo', '涛': 'tao',
    '湖': 'hu', '海': 'hai', '江': 'jiang', '河': 'he', '溪': 'xi',
    '德': 'de', '仁': 'ren', '义': 'yi', '礼': 'li', '智': 'zhi',
    '信': 'xin', '忠': 'zhong', '孝': 'xiao', '廉': 'lian',
    '一': 'yi', '二': 'er', '三': 'san', '四': 'si', '五': 'wu',
    '六': 'liu', '七': 'qi', '八': 'ba', '九': 'jiu', '十': 'shi',
    '百': 'bai', '千': 'qian', '万': 'wan', '亿': 'yi',
    '日': 'ri', '时': 'shi', '分': 'fen', '秒': 'miao', '刻': 'ke',
    '年': 'nian', '月': 'yue', '周': 'zhou', '天': 'tian',
    '今': 'jin', '明': 'ming', '昨': 'zuo', '朝': 'chao', '夕': 'xi',
    '旦': 'dan', '昏': 'hun', '夜': 'ye', '午': 'wu', '晨': 'chen',
    '晖': 'hui', '春': 'chun', '夏': 'xia', '秋': 'qiu', '冬': 'dong',
    '春': 'chun', '晖': 'hui', '梅': 'mei', '兰': 'lan', '竹': 'zhu',
    '菊': 'ju', '松': 'song', '柏': 'bai', '杉': 'shan', '桐': 'tong',
    '凤': 'feng', '凰': 'huang', '鸾': 'luan', '鹏': 'peng', '鹰': 'ying',
    '龙': 'long', '虎': 'hu', '豹': 'bao', '熊': 'xiong', '狮': 'shi',
    '凤': 'feng', '麟': 'lin', '麒': 'qi', '龟': 'gui', '鹤': 'he',
    '鱼': 'yu', '鸟': 'niao', '虫': 'chong', '马': 'ma', '牛': 'niu',
    '羊': 'yang', '猪': 'zhu', '狗': 'gou', '猫': 'mao', '鼠': 'shu',
    '梅': 'mei', '兰': 'lan', '竹': 'zhu', '菊': 'ju',
    '琴': 'qin', '棋': 'qi', '书': 'shu', '画': 'hua', '诗': 'shi',
    '酒': 'jiu', '茶': 'cha', '花': 'hua', '香': 'xiang',
    '盈': 'ying', '亏': 'kui', '圆': 'yuan', '缺': 'que',
    '成': 'cheng', '败': 'bai', '得': 'de', '失': 'shi',
    '进': 'jin', '退': 'tui', '攻': 'gong', '守': 'shou',
    '动': 'dong', '静': 'jing', '快': 'kuai', '慢': 'man',
    '多': 'duo', '少': 'shao', '大': 'da', '小': 'xiao',
    '长': 'chang', '短': 'duan', '高': 'gao', '低': 'di',
    '远': 'yuan', '近': 'jin', '深': 'shen', '浅': 'qian',
    '粗': 'cu', '细': 'xi', '宽': 'kuan', '窄': 'zhai',
    '重': 'zhong', '轻': 'qing', '厚': 'hou', '薄': 'bo',
    '软': 'ruan', '硬': 'ying', '热': 're', '冷': 'leng',
    '明': 'ming', '暗': 'an', '亮': 'liang', '黑': 'hei',
    '干': 'gan', '湿': 'shi', '清': 'qing', '浊': 'zhuo',
    '新': 'xin', '旧': 'jiu', '老': 'lao', '幼': 'you',
    '好': 'hao', '坏': 'huai', '美': 'mei', '丑': 'chou',
    '真': 'zhen', '假': 'jia', '善': 'shan', '恶': 'e',
    '是': 'shi', '非': 'fei', '对': 'dui', '错': 'cuo',
    '富': 'fu', '穷': 'qiong', '贵': 'gui', '贱': 'jian',
    '吉': 'ji', '凶': 'xiong', '祸': 'huo', '福': 'fu',
    '智': 'zhi', '愚': 'yu', '聪': 'cong', '笨': 'ben',
    '明': 'ming', '暗': 'an', '聪': 'cong', '钝': 'dun',
    '易': 'yi', '难': 'nan', '深': 'shen', '浅': 'qian',
    '早': 'zao', '晚': 'wan', '迟': 'chi', '速': 'su',
    '久': 'jiu', '暂': 'zan', '长': 'chang', '短': 'duan',
    '常': 'chang', '偶': 'ou', '稀': 'xi', '罕': 'han',
    '丰': 'feng', '欠': 'qian', '足': 'zu', '亏': 'kui',
    '裕': 'yu', '紧': 'jin', '松': 'song', '紧': 'jin',
    '公': 'gong', '私': 'si', '义': 'yi', '利': 'li',
    '直': 'zhi', '曲': 'qu', '正': 'zheng', '偏': 'pian',
    '圆': 'yuan', '方': 'fang', '平': 'ping', '直': 'zhi',
    '白': 'bai', '黑': 'hei', '红': 'hong', '黄': 'huang',
    '蓝': 'lan', '绿': 'lv', '紫': 'zi', '灰': 'hui',
    '酸': 'suan', '甜': 'tian', '苦': 'ku', '辣': 'la',
    '咸': 'xian', '淡': 'dan', '香': 'xiang', '臭': 'chou',
    '温': 'wen', '热': 're', '凉': 'liang', '冷': 'leng',
    '饱': 'bao', '饿': 'e', '渴': 'ke', '醉': 'zui',
    '醒': 'xing', '睡': 'shui', '梦': 'meng',
    '喜': 'xi', '怒': 'nu', '哀': 'ai', '乐': 'le',
    '悲': 'bei', '恐': 'kong', '惊': 'jing', '爱': 'ai',
    '恨': 'hen', '思': 'si', '念': 'nian', '想': 'xiang',
    '愿': 'yuan', '望': 'wang', '盼': 'pan', '望': 'wang',
    '飞': 'fei', '走': 'zou', '跑': 'pao', '跳': 'tiao',
    '爬': 'pa', '游': 'you', '泳': 'yong', '潜': 'qian',
    '卧': 'wo', '坐': 'zuo', '立': 'li', '行': 'xing',
    '看': 'kan', '听': 'ting', '说': 'shuo', '读': 'du',
    '写': 'xie', '算': 'suan', '画': 'hua', '唱': 'chang',
    '舞': 'wu', '弹': 'tan', '奏': 'zou', '拍': 'pai',
    '买': 'mai', '卖': 'mai', '送': 'song', '收': 'shou',
    '借': 'jie', '还': 'huan', '给': 'gei', '拿': 'na',
    '放': 'fang', '挂': 'gua', '摆': 'bai', '装': 'zhuang',
    '卸': 'xie', '背': 'bei', '扛': 'kang', '提': 'ti',
    '拉': 'la', '推': 'tui', '拖': 'tuo', '抱': 'bao',
    '打': 'da', '抓': 'zhua', '握': 'wo', '摇': 'yao',
    '推': 'tui', '拉': 'la', '压': 'ya', '挤': 'ji',
    '敲': 'qiao', '拍': 'pai', '打': 'da', '踢': 'ti',
    '跑': 'pao', '跳': 'tiao', '走': 'zou', '冲': 'chong',
    '挤': 'ji', '过': 'guo', '进': 'jin', '出': 'chu',
    '入': 'ru', '上': 'shang', '下': 'xia', '起': 'qi',
    '落': 'luo', '升': 'sheng', '降': 'jiang', '升': 'sheng',
    '飞': 'fei', '落': 'luo', '飘': 'piao', '流': 'liu',
    '转': 'zhuan', '动': 'dong', '摇': 'yao', '摆': 'bai',
    '转': 'zhuan', '弯': 'wan', '直': 'zhi', '扭': 'niu',
    '伸': 'shen', '缩': 'suo', '张': 'zhang', '闭': 'bi',
    '开': 'kai', '关': 'guan', '启': 'qi', '闭': 'bi',
    '笑': 'xiao', '哭': 'ku', '喊': 'han', '叫': 'jiao',
    '唱': 'chang', '叫': 'jiao', '喊': 'han', '吼': 'hou',
    '问': 'wen', '答': 'da', '谈': 'tan', '说': 'shuo',
    '讲': 'jiang', '告': 'gao', '诉': 'su', '议': 'yi',
    '论': 'lun', '评': 'ping', '批': 'pi', '判': 'pan',
    '夸': 'kua', '奖': 'jiang', '惩': 'cheng', '罚': 'fa',
    '奖': 'jiang', '励': 'li', '鼓': 'gu', '励': 'li',
    '赞': 'zan', '美': 'mei', '批': 'pi', '评': 'ping',
    '爱': 'ai', '恨': 'hen', '喜': 'xi', '怒': 'nu',
    '忧': 'you', '愁': 'chou', '悲': 'bei', '乐': 'le',
    '心': 'xin', '意': 'yi', '志': 'zhi', '愿': 'yuan',
    '梦': 'meng', '想': 'xiang', '念': 'nian', '思': 'si',
    '智': 'zhi', '慧': 'hui', '才': 'cai', '能': 'neng',
    '力': 'li', '气': 'qi', '神': 'shen', '魂': 'hun',
    '体': 'ti', '魄': 'po', '貌': 'mao', '容': 'rong',
    '颜': 'yan', '面': 'mian', '脸': 'lian', '眼': 'yan',
    '耳': 'er', '鼻': 'bi', '口': 'kou', '舌': 'she',
    '手': 'shou', '足': 'zu', '腿': 'tui', '脚': 'jiao',
    '臂': 'bi', '指': 'zhi', '甲': 'jia', '爪': 'zhua',
    '皮': 'pi', '毛': 'mao', '发': 'fa', '骨': 'gu',
    '血': 'xue', '心': 'xin', '肝': 'gan', '肺': 'fei',
    '肾': 'shen', '胃': 'wei', '肠': 'chang', '脑': 'nao',
    '良': 'liang', '善': 'shan', '美': 'mei', '好': 'hao',
    '坏': 'huai', '恶': 'e', '丑': 'chou', '臭': 'chou',
    '新': 'xin', '旧': 'jiu', '老': 'lao', '幼': 'you',
    '尊': 'zun', '敬': 'jing', '爱': 'ai', '恨': 'hen',
    '恭': 'gong', '敬': 'jing', '谦': 'qian', '虚': 'xu',
    '骄': 'jiao', '傲': 'ao', '懒': 'lan', '惰': 'duo',
    '勤': 'qin', '劳': 'lao', '努': 'nu', '力': 'li',
    '俭': 'jian', '朴': 'pu', '奢': 'she', '侈': 'chi',
    '光': 'guang', '荣': 'rong', '耻': 'chi', '辱': 'ru',
    '誉': 'yu', '毁': 'hui', '赞': 'zan', '誉': 'yu',
    '批': 'pi', '评': 'ping', '议': 'yi', '论': 'lun',
    '建': 'jian', '造': 'zao', '筑': 'zhu', '设': 'she',
    '装': 'zhuang', '修': 'xiu', '理': 'li', '养': 'yang',
    '维': 'wei', '护': 'hu', '管': 'guan', '理': 'li',
    '保': 'bao', '安': 'an', '全': 'quan', '稳': 'wen',
    '危': 'wei', '险': 'xian', '难': 'nan', '易': 'yi',
    '苦': 'ku', '乐': 'le', '哀': 'ai', '怨': 'yuan',
    '恨': 'hen', '爱': 'ai', '喜': 'xi', '怒': 'nu',
    '高': 'gao', '兴': 'xing', '兴': 'xing', '低': 'di',
    '落': 'luo', '升': 'sheng', '提': 'ti', '升': 'sheng',
    '降': 'jiang', '加': 'jia', '减': 'jian', '乘': 'cheng',
    '除': 'chu', '加': 'jia', '减': 'jian', '乘': 'cheng',
    '父': 'fu', '母': 'mu', '哥': 'ge', '弟': 'di',
    '姐': 'jie', '妹': 'mei', '爷': 'ye', '奶': 'nai',
    '外': 'wai', '公': 'gong', '婆': 'po', '丈': 'zhang',
    '伯': 'bo', '叔': 'shu', '姑': 'gu', '舅': 'jiu',
    '姨': 'yi', '侄': 'zhi', '甥': 'sheng', '孙': 'sun',
    '学': 'xue', '生': 'sheng', '老': 'lao', '师': 'shi',
    '教': 'jiao', '授': 'shou', '育': 'yu', '才': 'cai',
    '专': 'zhuan', '家': 'jia', '博': 'bo', '士': 'shi',
    '硕': 'shuo', '士': 'shi', '博': 'bo', '士': 'shi',
    '本': 'ben', '科': 'ke', '硕': 'shuo', '博': 'bo',
    '理': 'li', '工': 'gong', '文': 'wen', '理': 'li',
    '医': 'yi', '学': 'xue', '法': 'fa', '学': 'xue',
    '教': 'jiao', '育': 'yu', '学': 'xue', '艺': 'yi',
    '术': 'shu', '工': 'gong', '商': 'shang', '农': 'nong',
    '兵': 'bing', '警': 'jing', '官': 'guan', '员': 'yuan',
    '员': 'yuan', '工': 'gong', '师': 'shi', '生': 'sheng',
    '家': 'jia', '长': 'zhang', '员': 'yuan', '工': 'gong',
}


def get_pinyin_full(ch: str) -> str:
    """获取单个汉字的全拼（小写）。无字典覆盖时返回 'x'。"""
    if not ch or not '\u4e00' <= ch <= '\u9fff':
        return ''
    # 优先名字字典（更丰富），其次姓氏字典
    py = _GIVEN_NAME_PINYIN.get(ch) or _SURNAME_PINYIN.get(ch)
    if py:
        return py
    return 'x'  # fallback: 字典未覆盖


def get_pinyin_first_letter(ch: str) -> str:
    """获取单个汉字的拼音首字母（1 个字符）。"""
    full = get_pinyin_full(ch)
    if not full:
        return ''
    return full[0]


def _is_known_surname(ch: str) -> bool:
    """严格判断一个汉字是否在我们的姓氏字典里（专有姓氏）"""
    return ch in _SURNAME_PINYIN


def generate_username(real_name: str) -> str:
    """根据姓名生成账号。
    规则：名的所有汉字首字母 + 姓全拼（姓在最后）
    例子：
        张三      → s + zhang = szhang
        李俊峰    → jf + li = jfli
        王小明    → xm + wang = xmwang
        欧阳明    → m + ouyang = mouyang  （复姓）
    失败 fallback: 长度 < 2 时直接用拼音首字母
    """
    if not real_name:
        return ''
    real_name = real_name.strip().replace(' ', '')

    if len(real_name) < 2:
        # 1 字：直接用全拼
        return get_pinyin_full(real_name[0]) or 'user'

    # 中文姓名：姓在前、名在后（与用户例子一致：szhang = 三首字母 + 张全拼）
    # 拆分策略：
    #   - 复姓：开头 2 字是复姓 → 姓=前 2 字, 名=后续
    #   - 单字姓：开头 1 字是姓 → 姓=第 1 字, 名=后续
    surname_part = ''
    name_part = ''

    # 先尝试复姓（开头 2 字）
    if len(real_name) >= 2 and _is_known_surname(real_name[:2]):
        surname_part = _SURNAME_PINYIN[real_name[:2]]
        name_part = real_name[2:]
    else:
        # 单字姓：第 1 字必须是"已知姓氏"
        first_char = real_name[0]
        if _is_known_surname(first_char):
            surname_part = _SURNAME_PINYIN[first_char]
            name_part = real_name[1:]
        else:
            # 第 1 字不在姓氏字典里：从右往左找"已知姓氏"（兜底）
            # 例如"张三"中"张"是姓，但"三"不是 → 我们能识别出"张"在 index 0
            for i in range(len(real_name) - 1, -1, -1):
                if _is_known_surname(real_name[i]):
                    # 姓 = real_name[i], 名 = real_name[:i] + real_name[i+1:]
                    surname_part = _SURNAME_PINYIN[real_name[i]]
                    name_part = real_name[:i] + real_name[i+1:]
                    break

    if not surname_part:
        # 没识别出姓：整字全拼 + 末字首字母（保守回退）
        full_pinyin = ''.join(get_pinyin_full(ch) for ch in real_name)
        given_initials = ''.join(get_pinyin_first_letter(ch) for ch in real_name if ch.strip())
        return ((full_pinyin + given_initials[-1:]).lower() if full_pinyin else (given_initials or 'user'))

    # 名 → 每个汉字首字母
    given_initials = ''.join(get_pinyin_first_letter(ch) for ch in name_part if ch.strip())

    # 顺序：名首字母 + 姓全拼（姓在最后）
    return (given_initials + surname_part).lower()


def make_unique_username(base: str, exists_fn) -> str:
    """在 base 基础上加 01/02/... 后缀，确保唯一
    exists_fn: callable(username) -> bool
    """
    if not base:
        return 'user'
    candidate = base
    n = 0
    while exists_fn(candidate):
        n += 1
        candidate = f'{base}{n:02d}'
        if n > 99:
            # 极端情况兜底
            candidate = f'{base}_{int(time.time())}'
            break
    return candidate
