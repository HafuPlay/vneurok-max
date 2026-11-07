import hashlib,hmac,json,time
from pathlib import Path
import tempfile,unittest
from urllib.parse import urlencode
from vneurok.core import Store,DomainError
from vneurok.max_api import validate_init_data,accept_webhook,flush_outbox,process_bot_update,flush_bot_outbox

TOKEN='test-only-not-a-real-token'

def signed(**overrides):
    values={'auth_date':str(int(time.time())),'user':json.dumps({'id':12345,'first_name':'A + B'},separators=(',',':'))}
    values.update(overrides)
    secret=hmac.new(b'WebAppData',TOKEN.encode(),hashlib.sha256).digest()
    values['hash']=hmac.new(secret,'\n'.join(f'{k}={v}' for k,v in sorted(values.items())).encode(),hashlib.sha256).hexdigest()
    return urlencode(values)

class MaxTests(unittest.TestCase):
    def test_valid_signature(self): self.assertEqual(validate_init_data(signed(),TOKEN),12345)
    def test_signature_tamper(self):
        with self.assertRaises(DomainError): validate_init_data(signed().replace('12345','12346'),TOKEN)
    def test_duplicate_hash_rejected(self):
        with self.assertRaises(DomainError): validate_init_data(signed()+'&hash='+'a'*64,TOKEN)
    def test_duplicate_user_rejected(self):
        with self.assertRaises(DomainError): validate_init_data(signed()+'&user=%7B%22id%22%3A2%7D',TOKEN)
    def test_stale_and_future_rejected(self):
        for timestamp in [int(time.time())-4000,int(time.time())+100]:
            with self.assertRaises(DomainError): validate_init_data(signed(auth_date=str(timestamp)),TOKEN)
    def test_no_type_coercion(self):
        for uid in [True,'12345',0]:
            with self.assertRaises(DomainError): validate_init_data(signed(user=json.dumps({'id':uid})),TOKEN)
    def test_unknown_school_user_not_autoregistered(self):
        with tempfile.TemporaryDirectory() as d:
            store=Store(Path(d)/'test.db')
            with self.assertRaises(DomainError): store.max_user(12345)
            with store.connection() as db: self.assertEqual(db.execute('SELECT count(*) FROM users').fetchone()[0],0)
    def test_webhook_secret_dedupe_and_delivery_uncertainty(self):
        with tempfile.TemporaryDirectory() as d:
            store=Store(Path(d)/'test.db'); store.seed_demo()
            with store.connection(True) as db: db.execute("UPDATE users SET max_id='12345' WHERE id='student-author'")
            payload={'update_type':'bot_started','timestamp':1000,'user':{'user_id':12345}}
            with self.assertRaises(DomainError): accept_webhook(store,payload,'wrong','expected','https://example.test')
            self.assertTrue(accept_webhook(store,payload,'expected','expected','https://example.test')['queued'])
            self.assertTrue(accept_webhook(store,payload,'expected','expected','https://example.test')['duplicate'])
            self.assertEqual(flush_outbox(store)['sent'],0)
            calls=[]
            def failing(*args): calls.append(args); raise TimeoutError()
            result=flush_outbox(store,TOKEN,True,failing)
            self.assertEqual(result['uncertain'],1)
            self.assertEqual(flush_outbox(store,TOKEN,True,failing)['uncertain'],0)
            self.assertEqual(len(calls),1)
    def test_successful_delivery_recorded(self):
        with tempfile.TemporaryDirectory() as d:
            store=Store(Path(d)/'test.db'); store.seed_demo()
            with store.connection(True) as db: db.execute("UPDATE users SET max_id='12345' WHERE id='student-author'")
            accept_webhook(store,{'update_type':'bot_started','timestamp':1001,'user':{'user_id':12345}},'s','s','https://example.test')
            calls=[]; result=flush_outbox(store,TOKEN,True,lambda *args:calls.append(args))
            self.assertEqual(result['sent'],1); self.assertEqual(len(calls),1)
            self.assertEqual(flush_outbox(store)['pending'],0)

class BotWebhookTests(unittest.TestCase):
    def test_event_to_reply_and_safe_retry(self):
        from vneurok.bot import BotRouter
        with tempfile.TemporaryDirectory() as d:
            store=Store(Path(d)/'school.db'); router=BotRouter(Path(d)/'demo',store)
            payload={'update_type':'message_created','message':{'sender':{'user_id':123},'recipient':{'chat_type':'dialog'},'body':{'mid':'m1','text':'/demo'}}}
            self.assertTrue(process_bot_update(store,router,payload,'s','s')['queued'])
            self.assertTrue(process_bot_update(store,router,payload,'s','s')['duplicate'])
            calls=[]
            self.assertEqual(flush_bot_outbox(store,TOKEN,lambda *a:calls.append(a))['sent'],1)
            self.assertEqual(flush_bot_outbox(store,TOKEN,lambda *a:calls.append(a))['sent'],0)
            self.assertEqual(len(calls),1)
            self.assertIn('пример',calls[0][1])
    def test_group_and_bad_secret_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            store=Store(Path(d)/'school.db')
            with self.assertRaises(DomainError): process_bot_update(store,None,{},'wrong','s')
            payload={'update_type':'message_created','message':{'recipient':{'chat_type':'chat'}}}
            self.assertTrue(process_bot_update(store,None,payload,'s','s')['ignored'])
    def test_send_timeout_not_replayed(self):
        with tempfile.TemporaryDirectory() as d:
            store=Store(Path(d)/'school.db')
            with store.connection(True) as db: db.execute("INSERT INTO bot_outbox(event_key,max_user_id,text,created_at) VALUES('k',123,'Привет','now')")
            def timeout(*a): raise TimeoutError()
            self.assertEqual(flush_bot_outbox(store,TOKEN,timeout)['uncertain'],1)
            self.assertEqual(flush_bot_outbox(store,TOKEN,timeout)['uncertain'],0)

if __name__=='__main__': unittest.main()
