"""
OKX REST API 客户端封装
基于 python-okx SDK，提供统一的交易接口调用
"""

import logging
from typing import Optional, Dict, Any, List
from django.conf import settings

from okx import Account, MarketData, Trade, PublicData, Funding
from okx.exceptions import OkxAPIException, OkxRequestException

from core.exceptions import OKXClientError, OKXAuthError

logger = logging.getLogger(__name__)


class OKXClient:
    """OKX API 统一客户端"""

    def __init__(self, api_key: str = None, api_secret: str = None,
                 passphrase: str = None, flag: str = None, debug: bool = False):
        config = settings.OKX_CONFIG
        self.api_key = api_key or config['API_KEY']
        self.api_secret = api_secret or config['API_SECRET']
        self.passphrase = passphrase or config['PASSPHRASE']
        self.flag = flag or config['FLAG']
        self.debug = debug or config['DEBUG']

        if not all([self.api_key, self.api_secret, self.passphrase]):
            logger.warning('OKX API 凭证未完整配置，仅可使用公共接口')

        # 懒加载模块占位（实际实例在 property 首次访问时创建）
        self._account = None
        self._trade = None
        self._market = None
        self._public = None
        self._funding = None

    def has_credentials(self) -> bool:
        """判断是否已配置完整凭证（可发起交易请求）"""
        return bool(self.api_key and self.api_secret and self.passphrase)

    def require_credentials(self, action: str = '交易'):
        """强制要求凭证完整，否则抛出友好错误"""
        if not self.has_credentials():
            raise OKXClientError(
                f'未配置 OKX API 凭证，无法执行{action}。'
                '请先在「系统设置-API凭证」中配置当前环境的 API Key/Secret/Passphrase。'
            )

    # -------- 懒加载模块 --------
    @property
    def account(self) -> Account.AccountAPI:
        if self._account is None:
            self._account = Account.AccountAPI(
                api_key=self.api_key,
                api_secret_key=self.api_secret,
                passphrase=self.passphrase,
                flag=self.flag,
                debug=self.debug,
            )
        return self._account

    @property
    def trade(self) -> Trade.TradeAPI:
        if self._trade is None:
            self._trade = Trade.TradeAPI(
                api_key=self.api_key,
                api_secret_key=self.api_secret,
                passphrase=self.passphrase,
                flag=self.flag,
                debug=self.debug,
            )
        return self._trade

    @property
    def market(self) -> MarketData.MarketAPI:
        if self._market is None:
            self._market = MarketData.MarketAPI(
                api_key=self.api_key,
                api_secret_key=self.api_secret,
                passphrase=self.passphrase,
                flag=self.flag,
                debug=self.debug,
            )
        return self._market

    @property
    def public(self) -> PublicData.PublicAPI:
        if self._public is None:
            self._public = PublicData.PublicAPI(
                api_key=self.api_key,
                api_secret_key=self.api_secret,
                passphrase=self.passphrase,
                flag=self.flag,
                debug=self.debug,
            )
        return self._public

    @property
    def funding(self) -> Funding.FundingAPI:
        if self._funding is None:
            self._funding = Funding.FundingAPI(
                api_key=self.api_key,
                api_secret_key=self.api_secret,
                passphrase=self.passphrase,
                flag=self.flag,
                debug=self.debug,
            )
        return self._funding

    # -------- 通用请求安全层 --------
    def _safe_call(self, func, *args, **kwargs):
        """安全的 API 调用，统一异常处理"""
        try:
            result = func(*args, **kwargs)
            if isinstance(result, dict) and result.get('code') != '0':
                error_msg = result.get('msg', 'Unknown OKX API error')
                logger.error(f'OKX API error: code={result.get("code")}, msg={error_msg}')
                raise OKXClientError(f'OKX API error [{result.get("code")}]: {error_msg}')
            return result
        except OkxAPIException as e:
            logger.error(f'OKX API exception: {e}')
            raise OKXClientError(str(e)) from e
        except OkxRequestException as e:
            logger.error(f'OKX request exception: {e}')
            raise OKXClientError(f'Network error: {e}') from e

    # ==================== 行情接口 ====================
    def get_ticker(self, inst_id: str) -> Dict:
        """获取单个产品行情"""
        return self._safe_call(self.market.get_ticker, instId=inst_id)

    def get_tickers(self, inst_type: str = 'SPOT') -> Dict:
        """获取所有产品行情"""
        return self._safe_call(self.market.get_tickers, instType=inst_type)

    def get_candlesticks(self, inst_id: str, bar: str = '1H',
                         limit: int = 100, after: str = '', before: str = '') -> Dict:
        """获取K线数据"""
        return self._safe_call(
            self.market.get_candlesticks, instId=inst_id,
            bar=bar, limit=str(limit), after=after, before=before
        )

    def get_history_candlesticks(self, inst_id: str, bar: str = '1H',
                                  limit: int = 100, after: str = '', before: str = '') -> Dict:
        """获取历史K线（最多1440根）"""
        return self._safe_call(
            self.market.get_history_candlesticks, instId=inst_id,
            bar=bar, limit=str(limit), after=after, before=before
        )

    def get_orderbook(self, inst_id: str, sz: int = 20) -> Dict:
        """获取深度数据"""
        return self._safe_call(self.market.get_orderbook, instId=inst_id, sz=str(sz))

    def get_index_candlesticks(self, inst_id: str, bar: str = '1H',
                                limit: int = 100, after: str = '', before: str = '') -> Dict:
        """获取指数K线"""
        return self._safe_call(
            self.market.get_index_candlesticks, instId=inst_id,
            bar=bar, limit=str(limit), after=after, before=before
        )

    # ==================== 交易接口 ====================
    def place_order(self, inst_id: str, td_mode: str, side: str,
                    ord_type: str, sz: str, px: str = '',
                    pos_side: str = '', tgt_ccy: str = '',
                    reduce_only: bool = False, client_oid: str = '') -> Dict:
        """下单"""
        params = {
            'instId': inst_id,
            'tdMode': td_mode,  # cash, cross, isolated
            'side': side,       # buy, sell
            'ordType': ord_type,  # market, limit, post_only, fok, ioc
            'sz': sz,
            'px': px,
        }
        if pos_side:
            params['posSide'] = pos_side
        if tgt_ccy:
            params['tgtCcy'] = tgt_ccy
        if reduce_only:
            params['reduceOnly'] = True
        if client_oid:
            params['clOrdId'] = client_oid

        return self._safe_call(self.trade.place_order, **params)

    def place_batch_orders(self, orders: List[Dict]) -> Dict:
        """批量下单"""
        return self._safe_call(self.trade.place_multiple_orders, orders_data=orders)

    def place_algo_order(self, inst_id: str, td_mode: str, side: str,
                         sz: str, ord_type: str = 'conditional',
                         trigger_px: str = '', px: str = '',
                         tp_trigger_px: str = '', tp_order_px: str = '',
                         sl_trigger_px: str = '', sl_order_px: str = '') -> Dict:
        """条件单/止盈止损单（OKX Algo 交易）"""
        params = {
            'instId': inst_id,
            'tdMode': td_mode,
            'side': side,
            'sz': sz,
            'ordType': ord_type,
        }
        if trigger_px:
            params['triggerPx'] = trigger_px
        if px:
            params['px'] = px
        if tp_trigger_px:
            params['tpTriggerPx'] = tp_trigger_px
            params['tpOrdPx'] = tp_order_px or '-1'
        if sl_trigger_px:
            params['slTriggerPx'] = sl_trigger_px
            params['slOrdPx'] = sl_order_px or '-1'
        return self._safe_call(self.trade.place_algo_order, **params)

    def cancel_order(self, inst_id: str, ord_id: str = '', cl_ord_id: str = '',
                     pos_side: str = '') -> Dict:
        """撤销订单

        注: 双向持仓模式（long_short_mode）下撤单必须携带 posSide，
        SDK 的 cancel_order 不支持该参数，需走底层请求。
        """
        params = {'instId': inst_id}
        if ord_id:
            params['ordId'] = ord_id
        if cl_ord_id:
            params['clOrdId'] = cl_ord_id
        if pos_side:
            from okx.consts import POST, CANCEL_ORDER
            params['posSide'] = pos_side
            return self._safe_call(
                self.trade._request_with_params, POST, CANCEL_ORDER, params
            )
        return self._safe_call(self.trade.cancel_order, **params)

    def cancel_batch_orders(self, orders: List[Dict]) -> Dict:
        """批量撤单"""
        return self._safe_call(self.trade.cancel_multiple_orders, orders_data=orders)

    def amend_order(self, inst_id: str, ord_id: str = '', cl_ord_id: str = '',
                    new_sz: str = '', new_px: str = '') -> Dict:
        """修改订单"""
        params = {'instId': inst_id}
        if ord_id:
            params['ordId'] = ord_id
        if cl_ord_id:
            params['clOrdId'] = cl_ord_id
        if new_sz:
            params['newSz'] = new_sz
        if new_px:
            params['newPx'] = new_px
        return self._safe_call(self.trade.amend_order, **params)

    def get_order(self, inst_id: str, ord_id: str = '', cl_ord_id: str = '') -> Dict:
        """查询订单详情"""
        params = {'instId': inst_id}
        if ord_id:
            params['ordId'] = ord_id
        if cl_ord_id:
            params['clOrdId'] = cl_ord_id
        return self._safe_call(self.trade.get_order, **params)

    def get_orders_pending(self, inst_type: str = '', inst_id: str = '',
                           ord_type: str = '', state: str = '') -> Dict:
        """查询未完成订单"""
        params = {}
        if inst_type:
            params['instType'] = inst_type
        if inst_id:
            params['instId'] = inst_id
        if ord_type:
            params['ordType'] = ord_type
        if state:
            params['state'] = state
        return self._safe_call(self.trade.get_orders_pending, **params)

    def get_orders_history(self, inst_type: str, inst_id: str = '',
                           ord_type: str = '', state: str = '',
                           limit: int = 100, after: str = '', before: str = '') -> Dict:
        """查询历史订单（近7天）"""
        params = {'instType': inst_type}
        if inst_id:
            params['instId'] = inst_id
        if ord_type:
            params['ordType'] = ord_type
        if state:
            params['state'] = state
        params.update({'limit': str(min(limit, 100)), 'after': after, 'before': before})
        return self._safe_call(self.trade.get_orders_history, **params)

    def close_position(self, inst_id: str, mgn_mode: str,
                       pos_side: str = '', ccy: str = '', auto_cxl: bool = False) -> Dict:
        """市价全平"""
        params = {'instId': inst_id, 'mgnMode': mgn_mode}
        if pos_side:
            params['posSide'] = pos_side
        if ccy:
            params['ccy'] = ccy
        if auto_cxl:
            params['autoCxl'] = 'true'
        return self._safe_call(self.trade.close_positions, **params)

    # ==================== 账户接口 ====================
    def get_account_balance(self) -> Dict:
        """获取账户余额"""
        return self._safe_call(self.account.get_account_balance)

    def get_positions(self, inst_type: str = '', inst_id: str = '',
                      pos_id: str = '') -> Dict:
        """获取持仓信息

        注意：OKX 的 get_positions 接口仅支持保证金类品种
        (MARGIN/SWAP/FUTURES/OPTION)。现货 SPOT 没有"持仓"概念，
        传入 instType=SPOT 会返回 51000 参数错误，故对 SPOT 或不支持的
        值不传 instType，由接口返回全部持仓（现货策略通常为空）。
        """
        params = {}
        cleaned = (inst_type or '').strip().upper()
        if cleaned in {'MARGIN', 'SWAP', 'FUTURES', 'OPTION'}:
            params['instType'] = cleaned
        if inst_id:
            params['instId'] = inst_id
        if pos_id:
            params['posId'] = pos_id
        return self._safe_call(self.account.get_positions, **params)

    def get_account_config(self) -> Dict:
        """获取账户配置"""
        return self._safe_call(self.account.get_account_config)

    def set_position_mode(self, pos_mode: str) -> Dict:
        """设置持仓模式: long_short_mode / net_mode"""
        return self._safe_call(self.account.set_position_mode, posMode=pos_mode)

    def set_leverage(self, lever: str, mgn_mode: str,
                     inst_id: str = '', ccy: str = '', pos_side: str = '') -> Dict:
        """设置杠杆倍数"""
        params = {'lever': lever, 'mgnMode': mgn_mode}
        if inst_id:
            params['instId'] = inst_id
        if ccy:
            params['ccy'] = ccy
        if pos_side:
            params['posSide'] = pos_side
        return self._safe_call(self.account.set_leverage, **params)

    def get_max_size(self, inst_id: str, td_mode: str,
                     ccy: str = '', px: str = '', leverage: str = '') -> Dict:
        """获取最大可买卖数量"""
        params = {'instId': inst_id, 'tdMode': td_mode}
        if ccy:
            params['ccy'] = ccy
        if px:
            params['px'] = px
        if leverage:
            params['leverage'] = leverage
        return self._safe_call(self.account.get_max_order_size, **params)

    # ==================== 公共数据接口 ====================
    def get_instruments(self, inst_type: str, uly: str = '',
                        inst_id: str = '') -> Dict:
        """获取交易产品信息"""
        params = {'instType': inst_type}
        if uly:
            params['uly'] = uly
        if inst_id:
            params['instId'] = inst_id
        return self._safe_call(self.public.get_instruments, **params)

    def get_funding_rate(self, inst_id: str) -> Dict:
        """获取资金费率"""
        return self._safe_call(self.public.get_funding_rate, instId=inst_id)

    def get_funding_rate_history(self, inst_id: str, limit: int = 100,
                                  after: str = '', before: str = '') -> Dict:
        """获取资金费率历史"""
        return self._safe_call(
            self.public.get_funding_rate_history, instId=inst_id,
            limit=str(limit), after=after, before=before
        )

    # ==================== 资金接口 ====================
    def get_currencies(self) -> Dict:
        """获取币种列表"""
        return self._safe_call(self.funding.get_currencies)

    def get_deposit_address(self, ccy: str) -> Dict:
        """获取充值地址"""
        return self._safe_call(self.funding.get_deposit_address, ccy=ccy)


# 按用户缓存的客户端
_user_clients: dict = {}


def reset_okx_client(user_id=None):
    """重置指定用户（或所有用户）的 OKX 客户端缓存"""
    global _user_clients
    if user_id is not None:
        _user_clients.pop(user_id, None)
    else:
        _user_clients.clear()


def get_okx_client(user=None) -> OKXClient:
    """获取 OKX 客户端；按当前系统环境选择对应凭证，支持按用户隔离"""
    global _user_clients
    user_id = user.id if user and user.is_authenticated else 0
    if user_id in _user_clients:
        return _user_clients[user_id]
    try:
        from apps.account.models import OKXCredential, SystemConfig
        if user and user.is_authenticated:
            config = SystemConfig.get_config(user=user)
            credential = OKXCredential.objects.filter(user=user, name=config.active_environment).first()
        else:
            config = SystemConfig.get_config()
            credential = OKXCredential.objects.filter(name=config.active_environment).first()
    except Exception:
        credential = None
    if credential:
        client = OKXClient(
            api_key=credential.api_key,
            api_secret=credential.api_secret,
            passphrase=credential.passphrase,
            flag=credential.flag,
        )
    else:
        client = OKXClient()
    _user_clients[user_id] = client
    return client


