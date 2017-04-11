# orm_test.py
import orm
from models import User, Blog, Comment
import asyncio, sys

loop = asyncio.get_event_loop()

@asyncio.coroutine
def test():
    yield from orm.create_pool(loop=loop, host='127.0.0.1', port=3306, user = 'root', password='111111', db='monkeyfarm')

    # findAll
    r = yield from User.findAll()
    print(r)

    # insert
    # u = User(name='Test3', email='test3@sina.com', password='333333', image='about:blank')
    # yield from u.save()
    
    # update
    # if len(r) != 0:
    for user in r:
        # if user.name == 'Test2':
        #     user.name = 'Test222'
        #     user.email = 'Test222@sina.com'
        #     user.admin = True
        #     yield from user.update()
        
        # delete
         if user.name == 'Test3':
               yield from user.remove()
    r = yield from User.findAll()
    print(r)

    yield from orm.destroy_pool()

loop.run_until_complete(test())
loop.close()
if loop.is_closed():
    sys.exit(0)

#def test():
#    yield from orm.create_pool(user='root', password='111111', database='monkeyfarm')
#    u = User(name='Test', email='test@sina.com', password='123456', image='about:blank')
#    yield from u.save()
#
#for x in test():
#    pass
