from model import Model
from datetime import datetime, date
from random import randint


class Courses(Model):

    def __init__(self, dbconn, cid=-1):
        Model.__init__(self, dbconn)
        self.cid = cid
        self.now = datetime.time(datetime.now())
        self.today = date.today()

    def get_course_name(self):
        query = 'select name from courses where cid = %s' % self.cid
        result = self.db.execute(query)
        return result.fetchone()[0]

    def get_students(self):
        query = ('select uid, name, family_name, email '
                 'from users, enrolled_in '
                 'where users.uid = enrolled_in.sid '
                 'and enrolled_in.cid = %s'
                 % self.cid)
        result = self.db.execute(query)
        return self.deproxy(result)

    def add_student(self, uni):
        uni = self.escape_string(uni)
        query = "select sid from students where uni = '%s'" % uni
        result = self.db.execute(query)

        if result.rowcount == 1:
            # found a student with uni, attempt to add to enrolled_in
            sid = result.fetchone()[0]
            try:
                query = 'insert into enrolled_in values (%s, %s)' \
                        % (sid, self.cid)
                self.db.execute(query)
                return 0
            except:
                # failed because already in enrolled_in
                return -2
        else:
            # invalid uni
            return -1

    def remove_student(self, uni):
        uni = self.escape_string(uni)
        query = "select sid from students where uni = '%s'" % uni
        result = self.db.execute(query)

        if result.rowcount == 1:
            # found a student with uni, attempt to remove from enrolled_in
            sid = result.fetchone()[0]

            query = ('select * from enrolled_in '
                     'where sid = %s and cid = %s'
                     % (sid, self.cid))
            result = self.db.execute(query)

            if result.rowcount == 1:
                query = 'delete from enrolled_in where sid = %s and cid = %s' \
                        % (sid, self.cid)
                self.db.execute(query)

                query = ('delete from attendance_records using sessions '
                         'where attendance_records.seid = sessions.seid '
                         'and attendance_records.sid = %s '
                         'and sessions.cid = %s'
                         % (sid, self.cid))
                self.db.execute(query)
                return 0
            else:
                # failed because it was not in enrolled_in to begin with
                return -3
        else:
            # invalid uni
            return -1

    def get_active_session(self):
        '''Return the seid of an active session if it exists,
        otherwise return -1.
        '''
        self.cid = self.escape_string(self.cid)
        query = ('select seid from sessions '
                 'where cid = %s '
                 "and expires > '%s' "
                 "and day >= '%s'"
                 % (self.cid, self.now, self.today))
        result = self.db.execute(query)
        return result.fetchone()[0] if result.rowcount == 1 else -1

    def close_session(self, seid):
        if seid == -1:
            return

        query = ('update sessions '
                 "set expires = '%s' "
                 'where seid = %s'
                 % (self.now, seid))
        self.db.execute(query)

        self.cid = self.escape_string(self.cid)
        query = 'update courses set active = 0 where cid = %s' % self.cid
        self.db.execute(query)

    def open_session(self):
        '''Opens a session for this course
        and returns the secret code for that session.
        '''
        # auto-generated secret code for now
        randsecret = randint(1000, 9999)
        self.cid = self.escape_string(self.cid)
        query = ('insert into sessions (cid, secret, expires, day) '
                 "values (%s, '%d', '%s', '%s')"
                 % (self.cid, randsecret, '23:59:59', self.today))
        self.db.execute(query)

        query = 'update courses set active = 1 where cid = %s' % self.cid
        self.db.execute(query)
        return randsecret

    def get_secret_code(self):
        query = ('select secret '
                 'from sessions, courses '
                 'where sessions.cid = courses.cid '
                 'and courses.cid = %s '
                 'and courses.active = 1 '
                 "and sessions.expires > '%s' "
                 "and sessions.day >= '%s'"
                 % (self.cid, self.now, self.today))
        result = self.db.execute(query)
        return int(result.fetchone()[0]) if result.rowcount == 1 else None

    def get_num_sessions(self):
        query = 'select * from sessions where cid = %s' % self.cid
        result = self.db.execute(query)
        return result.rowcount


    def get_teachers(self):
        query = '''
            SELECT u.uid, u.name, u.family_name, u.email
            FROM users u, teachers t, teaches te
            WHERE u.uid = t.tid AND t.tid = te.tid AND te.cid = %s
        ''' % (self.cid)
        result = self.db.execute(query)
        return self.deproxy(result)

    def add_teacher(self, email):
        email = self.escape_string(email)
        # check teacher exists as a user, if not, error
        getuser = '''
            SELECT uid FROM users where users.email = '%s'
        ''' % (email)
        user = self.db.execute(getuser)
        if user.rowcount < 1:
            return False, 'User %s not found' % (email)
        tid = user.fetchone()['uid']

        # check teacher exists as a teacher, if not, create
        try:
            insert_teacher = '''
                INSERT INTO teachers (tid) VALUES (%s)
            ''' % (tid)
            self.db.execute(insert_teacher)
        except:
            pass

        # add teaches entry
        try:
            insert_teaches = '''
                INSERT INTO TEACHES (tid, cid) VALUES (%s, %s)
            ''' % (tid, self.cid)
            self.db.execute(insert_teaches)
        except:
            return False, '%s is already a teacher in this class' % (email)

        return True, ''

    def remove_teacher(self, tid):
        delteacher = '''
            DELETE FROM teaches WHERE tid = %s and cid = %s
        ''' % (tid, self.cid)
        self.db.execute(delteacher)

    def get_sessions(self):
        # get seid, date, attendance for that day, and total enrollment in that class
        # for each session
        query = '''
            SELECT s.seid, s.day, COALESCE(ar.attendance, 0) AS attendance,
              COALESCE((SELECT count(*) FROM enrolled_in e WHERE e.cid = %s), 0) AS enrollment
            FROM sessions s LEFT OUTER JOIN (
              SELECT seid, count(sid) AS attendance
              FROM attendance_records
              GROUP BY seid) ar ON ar.seid = s.seid
            WHERE s.cid = %s
        ''' % (self.cid, self.cid)
        result = self.db.execute(query)
        return self.deproxy(result)
