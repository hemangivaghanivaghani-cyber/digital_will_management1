// SPDX-License-Identifier: MIT

pragma solidity ^0.8.20;



// NFT માટે જરૂરી OpenZeppelin લાઈબ્રેરીઓ

import "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";

import "@openzeppelin/contracts/access/Ownable.sol";



contract DigitalWill is ERC721URIStorage, Ownable {

    enum Status { Pending, Approved, Active }

    

    struct Will {

        string ipfsHash;

        address testator;

        uint256 approvalCount;

        Status status;

        bool isValue;

        uint256 nftTokenId; // NFT ID સ્ટોર કરવા માટે

    }

uint256 private _nextTokenId; // NFT ID કાઉન્ટર

    mapping(address => Will) public wills;

    mapping(address => mapping(address => bool)) public lawyerApprovals;

 // Constructor: NFT નું નામ 'DigitalWill' અને સિમ્બોલ 'DWILL'

    constructor() ERC721("DigitalWill", "DWILL") Ownable(msg.sender) {}

// Step 3: Record IPFS Hash

    function createWill(string memory _hash) public {

        wills[msg.sender] = Will(_hash, msg.sender, 0, Status.Pending, true, 0);

    }

// Step 4: Lawyer Approval Logic

    function approveWill(address _testator) public {

        require(wills[_testator].isValue, "Will does not exist");

        require(!lawyerApprovals[_testator][msg.sender], "Already approved");

        lawyerApprovals[_testator][msg.sender] = true;

        wills[_testator].approvalCount++;

    if (wills[_testator].approvalCount >= 2) {

            wills[_testator].status = Status.Approved;

        }

    }

// Step 5: Death Trigger + NFT Minting

    // જ્યારે એડમિન ટ્રીગર કરે, ત્યારે જ બેનિફિશિયરીના નામે NFT બનશે

    function triggerExecution(address _testator, address _beneficiary) public onlyOwner {

        require(wills[_testator].status == Status.Approved, "Will not approved by lawyers");

        

        wills[_testator].status = Status.Active;



        // --- NFT Minting Logic Start ---

        uint256 tokenId = _nextTokenId++;

        _safeMint(_beneficiary, tokenId); // બેનિફિશિયરીને NFT આપો

        _setTokenURI(tokenId, wills[_testator].ipfsHash); // NFT માં IPFS Hash સેટ કરો

        

        wills[_testator].nftTokenId = tokenId;

        // --- NFT Minting Logic End ---

    }



    // NFT ની વિગતો જોવા માટેનું ફંક્શન

    function getNFTDetails(address _testator) public view returns (uint256, string memory) {

        return (wills[_testator].nftTokenId, wills[_testator].ipfsHash);

    }

} 