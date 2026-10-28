import requests
def main():
    try:
        print('ACDV-Teams load')


        url = f"http://api.acdv-teams.io.vn/vi/projects/" 
        repon = requests.get(url) 
        print(repon)
        print(repon.get('data'))
        print('ACDV-Teams ok ')
    except Exception as e: 
     print(f'ACDV-Teams error {e}')
    
if __name__ == '__main__':
    main()
   