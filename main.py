import platform
import asyncio
import sys
import os

from curl_cffi.requests import AsyncSession
from better_proxy import Proxy
from web3 import Account
from loguru import logger

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

Account.enable_unaudited_hdwallet_features()

logger.remove()
logger.add(sink=sys.stdout, format="<white>{time:HH:mm:ss}</white>"
                                " | <level>{level: <8}</level>"
                                " | <cyan><b>{module}:{line}</b></cyan>"
                                " | <white><b>{message}</b></white>")
logger = logger.opt(colors=True)


USE_PROXY=True


class OmniNetwork:
    def __init__(self, thread: int, address: str, proxy: str) -> None:
        self.thread = thread
        self.address = address

        headers = {
            "accept": "*/*",
            "accept-language": "en-US,en",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "sec-ch-ua-platform": '"Windows"',
            "sec-ch-ua-mobile": "?0",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "connection": "keep-alive",
        }

        self.session = AsyncSession(impersonate="chrome120", proxy=proxy, headers=headers, verify=False)

    async def get_queryId(self) -> str:
        payload = {"pipelineVCName":"omniEcosystemScore",
                   "identifier":self.address,
                   "params":{
                       "walletAddresses":[self.address]
                       }
            }
        
        response = await self.session.post('https://omni-issuer-node.clique.tech/credentials', json=payload)
        answer = response.json()
        return answer['queryId']

    async def get_credentials(self) -> float|int:
        queryid = await self.get_queryId()

        while True:
            response = await self.session.get(f'https://omni-issuer-node.clique.tech/credentials/{queryid}')
            answer = response.json()
            if answer['status'] == 'Complete':
                return answer['data']['pipelines']['tokenQualified']
            await asyncio.sleep(3)

    async def check(self) -> float|int:
        balance = await self.get_credentials()
        if balance > 0:
            logger.info(f"Поток {self.thread} | Адрес кошелька: {self.address} | Баланс: <g>{balance}</g>")
        else:
            logger.info(f"Поток {self.thread} | Адрес кошелька {self.address} | Баланс: <r>{balance}</r>")
        return balance


class TaskManager:
    def __init__(self) -> None:
        self.wallets = TaskManager.read_file('data/wallets.txt')
        self.proxies = TaskManager.read_file('data/proxy.txt')

        self.proxy_index = 0
        self.lock = asyncio.Lock()
    
    @staticmethod
    def read_file(path: str) -> list:
        with open(path, 'r') as file:
            return [line.strip() for line in file.readlines() if line.strip()]

    @staticmethod
    def save_str_file(path: str, string: str):
        with open(path, 'a') as file:
            file.writelines(string + '\n')

    @staticmethod
    async def check_proxy(proxy: str) -> str|bool:
        try:
            async with AsyncSession(proxy=proxy, verify=False) as session:
                    await session.get('https://omni-issuer-node.clique.tech')
                    response = await session.get('https://api.ipify.org/?format=json', proxy=proxy, timeout=5)
                    answer = response.json()
        except Exception:
            return False
        else:
            return answer['ip']
            
    def get_proxy(self) -> str:
        proxy = self.proxies[self.proxy_index]
        proxy = Proxy.from_str(proxy if proxy.startswith('http://') else 'http://'+proxy).as_url
        self.proxy_index = (self.proxy_index + 1) % len(self.proxies)
        return proxy
    
    def get_address(self) -> str:
        wallet = self.wallets.pop(0)
        if len(wallet) == 42:
            return wallet
        elif len(wallet) == 66:
            return Account.from_key(wallet).address
        else:
            return Account.from_mnemonic(wallet).address
            
    async def initialization(self, thread: int):
        while True:
            if USE_PROXY:
                async with self.lock:
                    proxy = self.get_proxy()
                if not await TaskManager.check_proxy(proxy):
                    continue
            else:
                proxy = None

            async with self.lock:
                if not self.wallets:
                    break
                address = self.get_address()
                
            balance = await OmniNetwork(thread, address, proxy).check()
            async with self.lock:
                TaskManager.save_str_file("data/balance_info.txt", f'{address} - {balance} $OMNI')


async def main():
    os.system('cls' if os.name == 'nt' else 'clear')

    threads = int(input("Введите количество потоков: "))
    tm = TaskManager()

    tasks = []
    for thread in range(1, threads+1):
        tasks.append(asyncio.create_task(tm.initialization(thread)))

    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())


