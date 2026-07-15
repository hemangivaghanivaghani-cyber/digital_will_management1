import requests

def upload_to_ipfs(file_path):
    url = "https://api.pinata.cloud/pinning/pinFileToIPFS"
    # Tamari API keys Pinata dashboard mathi melvo
    headers = {
        'pinata_api_key': "YOUR_API_KEY",
        'pinata_secret_api_key': "YOUR_SECRET_KEY"
    }
    with open(file_path, 'rb') as file:
        response = requests.post(url, files={'file': file}, headers=headers)
        return response.json()['IpfsHash'] # Aa Hash return thashe