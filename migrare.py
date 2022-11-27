import sqlite3
import requests
from mee6_py_api import API
from mee6_py_api.api import check_http_response_for_errors, get_http_exception_for_status

import asyncio
import traceback

import aiohttp

class api2(API):
  async def send_get_request_and_get_response(self, url, params) -> dict:
    resp_headers = None
    resp_status = None
    try:
      async with aiohttp.ClientSession() as session:
        async with session.get(url=url, params=params) as resp:
          resp_headers = resp.headers
          resp_status = resp.status
          response = await resp.json(content_type=None)
          
    except Exception as e:
      if resp_status == 429: 
        await asyncio.sleep(float(resp_headers['Retry-After']))
        return await self.send_get_request_and_get_response(url, params)
      else:
        raise get_http_exception_for_status(resp_status)("Received an unknown bad response from server. \n"
                                                             "error: {} \n"
                                                             "status: {} \n"
                                                             "header: {}"
                                                             .format(e, resp_status, resp_headers))
    check_http_response_for_errors(response, resp_status, resp_headers)
    return response


async def main(db, conn):
	try:
		m6 = api2(954156776671043625)

		idx = 0
		while True:
			r = await m6.levels.get_leaderboard_page(idx)

			if r['page'] > idx: break 
			for usr in r["players"]:
				print(f"added {usr['username']}#{usr['discriminator']} level {usr['level']} xp {usr['xp']}")
				db.execute("INSERT INTO users VALUES (?, ?, ?)", (str(usr['id']), usr['level'], usr['xp']))
			conn.commit()
			idx += 1
	except:
		traceback.print_exc()
	finally:
		conn.commit()
		conn.close()

with sqlite3.connect("sqlite.db") as conn:
	global database, channel # yes IK, im to lasy to put it on the client Obj
	database = conn.cursor()

	
	asyncio.run(main(database, conn))
