from mega_sena_app import export_results
import logging
logging.basicConfig(level=logging.DEBUG)
print('Test export empty data (csv)')
export_results([], 'csv', 'tmp_empty', header=['A','B'])
print('Test export empty data (json)')
export_results([], 'json', 'tmp_empty_json')
print('Test export with normal data (csv)')
export_results([['2025-01-01',1,2,3,4,5,6]], 'csv', 'tmp_export_test', header=['Data','D1','D2','D3','D4','D5','D6'])