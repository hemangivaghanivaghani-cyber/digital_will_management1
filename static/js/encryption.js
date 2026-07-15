
function encryptWillData() {
    const assetData = document.getElementById('asset_details').value;
    const secretKey = "user-private-key";


    const encrypted = CryptoJS.AES.encrypt(assetData, secretKey).toString();
    
    document.getElementById('encrypted_preview').innerText = encrypted;
    console.log("Original Data:", assetData);
    console.log("Encrypted Data for Blockchain/IPFS:", encrypted);
}