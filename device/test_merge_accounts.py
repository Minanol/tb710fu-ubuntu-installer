import copy
import unittest
import merge_accounts as m


def databases(extra=False):
    result = {
        'passwd': [['root','x','0','0','root','/root','/bin/bash'],
                   ['daemon','x','1','1','daemon','/usr/sbin','/usr/sbin/nologin']],
        'shadow': [['root','!','','','','','','',''], ['daemon','*','','','','','','','']],
        'group': [['root','x','0',''], ['daemon','x','1','']],
        'gshadow': [['root','!','',''], ['daemon','!','','']],
    }
    if extra:
        result['passwd'].append(['newsvc','x','91','91','service','/nonexistent','/usr/sbin/nologin'])
        result['shadow'].append(['newsvc','*','','','','','','',''])
        result['group'].append(['newsvc','x','91',''])
        result['gshadow'].append(['newsvc','!','',''])
    return result


class MergeTests(unittest.TestCase):
    def test_preserves_existing_user_and_adds_new_system_account(self):
        old = databases()
        old['passwd'].append(['alice','x','1234','1234','Alice','/home/alice','/bin/bash'])
        old['shadow'].append(['alice','$testhash','','','','','','',''])
        old['group'].append(['alice','x','1234',''])
        old['gshadow'].append(['alice','!','',''])
        merged = m.merge(copy.deepcopy(old), databases(extra=True))
        self.assertIn(old['passwd'][-1], merged['passwd'])
        self.assertIn(old['shadow'][-1], merged['shadow'])
        self.assertIn('newsvc', [r[0] for r in merged['passwd']])

    def test_rejects_system_id_conflicts(self):
        old = databases()
        old['group'].append(['other','x','91',''])
        old['gshadow'].append(['other','!','',''])
        with self.assertRaisesRegex(ValueError, 'conflicts'):
            m.merge(old, databases(extra=True))

    def test_rejects_regular_user_in_release(self):
        new = databases()
        new['passwd'].append(['someone','x','1000','1000','','/home/someone','/bin/bash'])
        with self.assertRaisesRegex(ValueError, 'regular user'):
            m.merge(databases(), new)

    def test_rejects_existing_missing_shadow_entry(self):
        old = databases(); old['shadow'].pop()
        with self.assertRaisesRegex(ValueError, 'missing from shadow'):
            m.merge(old, databases())


if __name__ == '__main__':
    unittest.main()
