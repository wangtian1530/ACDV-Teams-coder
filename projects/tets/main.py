import requests
def main():
  
    url = f"http://api.acdv-teams.io.vn/vi/projects/" 
    repon = requests.get(url).json() 
    print(repon)
    print(repon.get('data'))
    

if __name__ == '__main__':
    main()
