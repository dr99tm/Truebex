// server/tests/contracts/project-log/action-finish.json
var action_finish_default = {
  op_id: "c40000000000f1110000000000000001",
  author: "019a2b3c4d5e7000a000000000000007",
  at: "2026-10-22T10:40:00.000Z",
  touched: [
    "16c7a345861d871eb38698b9b4016f8c"
  ],
  server_seq: 0,
  author_kind: "person",
  replica_id: "65d9df734a54806baae00ac40e73bfc9",
  base_seq: 0,
  kind: "action",
  name: "Paint wall",
  action: {
    tool: "fill",
    args: {
      target: "wall#16c7a345861d871eb38698b9b4016f8c",
      face: "left",
      finish: {
        kind: "paint",
        colour: "#C0392B"
      }
    },
    permission: "edit"
  }
};

// server/tests/contracts/project-log/action-move.json
var action_move_default = {
  op_id: "c10000000000a1100000000000000001",
  author: "019a2b3c4d5e7000a000000000000007",
  at: "2026-10-09T10:40:00.000Z",
  touched: [
    "dc643577cfb582fabd0d7f9edef6b30d"
  ],
  server_seq: 0,
  author_kind: "person",
  replica_id: "e5b8fcf3a2258635b7ee6740e3f81fa0",
  base_seq: 0,
  kind: "action",
  name: "Move wall",
  action: {
    tool: "move",
    args: {
      refs: [
        "wall#dc643577cfb582fabd0d7f9edef6b30d"
      ],
      by_mm: [
        0,
        600,
        0
      ]
    },
    permission: "edit"
  }
};

// server/tests/contracts/render-jobs/manifest-panorama.json
var manifest_panorama_default = {
  schema: "truebex-tiles/1",
  job_id: "c3000000000000000000000000000001",
  project_id: "fd1f65c522298d6fbd318103c6601118",
  at_seq: 0,
  app_version: "1.0.0",
  quality: "standard",
  views: [
    {
      view: "ecaf16d70fa5862cbba8f2288b9fd593",
      title: "bedroom",
      eye_mm: [
        6750,
        2500,
        1600
      ],
      face_px: 512,
      tile_px: 256,
      levels: [
        256,
        512
      ],
      faces: {
        n: {
          rendered: true,
          reason: "full",
          tiles: [
            [
              "849fba945c75643da309dc0c1ac42a24c35617ca91f4ee616d612d3fe50d1748"
            ],
            [
              "2daeb196e154035b0a165c0e76c6aa302c01cab6b1602d723e48fc83ec8b1394",
              "553f0c335b2c352bec85ad04d2b9b2c5750369b8f81b60e3fbf68da9002348b5",
              "c3d028c95a5c1391229f953e16d23565e034fe325f36c06eae22adbf33ebb41a",
              "ad0a1312e4a908d894d01ee5114b5de5b574e8196ad6b845833ded50a4a16786"
            ]
          ]
        },
        e: {
          rendered: true,
          reason: "full",
          tiles: [
            [
              "6f2f466d689e56ed3cda6a1347700daf47ce02828770dd6b9af4020706d873eb"
            ],
            [
              "b8a366fcfbb45e9164e72c280dcb00f3b7341b98a39f20a5c144104a5dcf0f77",
              "96fbe5c09b1bffea66256c10eb64cf9e94d6f5822dae0000d7e2a05ae8dab89f",
              "d1cf7df00766fbbe402c9b0ab458d1c2fc427d59319aa527c5841050bb3573f7",
              "789139b909154df3c6e16a6a37841b43a5c80b4bc133722eed77ef01b00d97bb"
            ]
          ]
        },
        s: {
          rendered: true,
          reason: "full",
          tiles: [
            [
              "bc46a146de2cf01fc915330882643a81bac351f4f4d4fc8f37f35f6471eabcd3"
            ],
            [
              "588dfb52d7d7f53a8b046fa4e65c48e814fa339a5ab024b3a41b0f5f59c7f9de",
              "aabb0c341fcfe957c7fa249c89c38f75dfab7345352c6087d6ac582062274189",
              "54d0f5a393d1e92fa0212aa0906d454fb993392ed4c1be03ef43bcd5e6d05715",
              "a565dfa53e6f30e7e04d87c134c5fff91dca297c23448625fe07dfbc8e9c0e8a"
            ]
          ]
        },
        w: {
          rendered: true,
          reason: "full",
          tiles: [
            [
              "2a031c9eed3da509bbdb897790a360cdce350958d741fb7a5b708db8887346e5"
            ],
            [
              "2fe4746c3fa839b6557b51179bdf44a026fe53f08d2668c66bc87711e9e2c66b",
              "c675dbe62392f5ddfa219cbb179c25a8fab6039c8d3451c2803d6440998b368a",
              "67197bfdcaf9ee969d241de8eb2e14ccaf4098a751fe3b3997306a59e400efaa",
              "c45c32009a8aee443dc4f6d1abb1091c08f3d7006dedc96bd505768393f61385"
            ]
          ]
        },
        u: {
          rendered: true,
          reason: "full",
          tiles: [
            [
              "5b3f598c29f3c6514b874460335354b6c959401e7bee02d7522a0ceeadd2c8f7"
            ],
            [
              "4cc130c81e032f53c908b98a98bc7d5fdf05ebf55fa11ebed8e971d054039b88",
              "ef27e12b6506a1a9a87042089dfd90c06f4b37e9d03cf746bb5d9d03980a509e",
              "2c2ad51f82085b5dd5dfdc6cb12df45c8779c0a3afde5a908d834c036e6b9e63",
              "7f5e77ae4427ec528344406828a6bd3c1c01b07ed3b631476f42bb505046059d"
            ]
          ]
        },
        d: {
          rendered: true,
          reason: "full",
          tiles: [
            [
              "e0f5b5b89a8df7b5ca6b710d642d0627718639607e004ee8c60a2865333ab3f0"
            ],
            [
              "65f27d7190a4b2b74acfe6b532f589212ba607844d8c3f628d791b97a2385d23",
              "b7ce97a59b2dd78b25bbf2fa8dc318f457ba6836077f5cb726d437af42e39670",
              "d5216e1dbfcf6a817c4470c949faae4558dba8d4f6f830d736eb1e97c60ca840",
              "daa3022f0bb00d78cf60bbc089a3c79542eb25f74f90990b16c4cb1f102fea87"
            ]
          ]
        }
      }
    },
    {
      view: "8388104cbff98d2dba07fd23c19c83b5",
      title: "entry",
      eye_mm: [
        2250,
        1e3,
        1600
      ],
      face_px: 512,
      tile_px: 256,
      levels: [
        256,
        512
      ],
      faces: {
        n: {
          rendered: true,
          reason: "full",
          tiles: [
            [
              "b24a417bd885a06fbe7576ff0b8c99652155813c3877e95d36260021ef17e2ce"
            ],
            [
              "f205b5910c28653191a2b33edfd48747336d65a7160f480b83ae02bd4cafccae",
              "a68e33aac3ac518b189948a26de96cb7445fba101e49cdabcc6b569fa7a51961",
              "69986c02735a104cb4390dca8628b7c2c2a91c50f38f07124e59ac0fa4f516a4",
              "a90d6bcd79f4819071e8bb0ecc60b08ee9d2eece54bbade002a11c179e33801f"
            ]
          ]
        },
        e: {
          rendered: true,
          reason: "full",
          tiles: [
            [
              "bfb052345f76b5c581eb25436a97b89cddd94e5f190e311c6adc9ccbceb04d78"
            ],
            [
              "2382a11b0fa19d36edac751909a955f10e006cd3c1f82ccd55647a1012aa5382",
              "eaa92b86e9795a545c831a7167553162838673626daa9a27ad3439d833aa61d7",
              "de5a17ed7ba69cd264eec13f87c13841504014f1b35a7e9502d7a2bb0862bee6",
              "e004c58e1790dcc7b8eaff4c0bb13ba21b3d1b6663d5d8f882645d3011e7f73d"
            ]
          ]
        },
        s: {
          rendered: true,
          reason: "full",
          tiles: [
            [
              "9ccdd93734b020f18638ee0422368887dfeb3b572b709463c4fe978c2c3f605d"
            ],
            [
              "47bdd8c3d411d7ba666e82ed10e867c3657a111cf9c2205859204670f4b6de2c",
              "a9e48786da49160b2f5df5e4345fb2df76a5fdb4eadd53361e3ed5fb3b36345e",
              "1b6776793b2207696a6cd6c4f3e3d8cea6b9ce37279327405f64e08f8a19f288",
              "4ca76b4d299562013a34b778e07807684e9947c206655fa4183f2855455fef68"
            ]
          ]
        },
        w: {
          rendered: true,
          reason: "full",
          tiles: [
            [
              "ea5245037df4f4e3bef61a9cc3ae431b0132ce15aa6a0a902a68005c82a0e0f5"
            ],
            [
              "ea11e259faa0ed7b006da27ec575d54498b98f2e15fd68797eb45bdb43783fbd",
              "faf229985c5509ad235c5d867da13b75202ac812e5f0ee9efbcb26f41a3c5a80",
              "b6a5b68655a9d6a895cd3513ed69fdfe034c7d915ea441f1448c82710a5ee0ca",
              "9ecec606e5f393c743fd326938bac8ed37c5a5d884b82e0845678c3dc566c6cd"
            ]
          ]
        },
        u: {
          rendered: true,
          reason: "full",
          tiles: [
            [
              "6589a11fb7bd30f92db0a82f79f9a6ac807b07e69715c98635818881ddef7de2"
            ],
            [
              "9386d56b7c941d7ce4276505c7ace33582b99e872b4f42959e38b798073072d2",
              "52f5e034e7023af75f8b1dd3da13cb62185bd29b3b4c38b1e7650e1de0590a26",
              "227d2c00860c91bca43b86e51be9b4f52c68650af9184f537e5001dba1e63459",
              "ca4d8e21917e863f3537fbe6c82539290c80e91497cdfa4ed36f8d5ce75ce997"
            ]
          ]
        },
        d: {
          rendered: true,
          reason: "full",
          tiles: [
            [
              "2f2d953665004a185c46911a3bba8b45974b674012408ea866664347e49e0dab"
            ],
            [
              "f0790b6fba566ffc7673b504a08f604fb6e634032ee72ad4d693b1c0aaa69b38",
              "b8460be3eec1f82cee53bd17ee6c1c4cfa0b990c4d6dadc4741a10b5603edd6a",
              "9f74a9ab2ccef97743849e00d9581e4c6d0c1f36df08a60eccafea0cfa0b9fb2",
              "5aed548b640eefde0df0ca034823042bf6cb4eb5caa53840a1dbb2d17043c0b0"
            ]
          ]
        }
      }
    },
    {
      view: "aee49319c0d48a7a953f247b52c948be",
      title: "living",
      eye_mm: [
        2250,
        2500,
        1600
      ],
      face_px: 512,
      tile_px: 256,
      levels: [
        256,
        512
      ],
      faces: {
        n: {
          rendered: true,
          reason: "full",
          tiles: [
            [
              "c3644de8f20287088d955aa5e53af3659ca1298204a5d8a82e6f16ef0f04801f"
            ],
            [
              "3e4eee7bfcb29b0d8d23e6cef60604affbdb694c91d2e1a9de43b6c5d90406f7",
              "68630fb497b81605ee62284bd6ac7375328ae83c68a8b578f61f6e5ae929f750",
              "1288c9eb40a6c72beed9a55e0e9a603a8ca1f2ab650196a42895977e64397d16",
              "43451faee5a2053e779d8b13f0aced2716b82dea48570c33270eeb124ef6b7ca"
            ]
          ]
        },
        e: {
          rendered: true,
          reason: "full",
          tiles: [
            [
              "717818ca3d58ef9e0e37c604d8ac94952f4eb74fb4829cf99265bf1e001ea575"
            ],
            [
              "6855eb0d9665dec3c11e2917cf7a35987de98df1926d82b2d24b2a3f8c49655b",
              "356d27411df32f480ed95a2ccf63e31a563e9e9051de2d437ddd8e9d4d8db9a5",
              "0986cc0425088d7acfdf91952a3262047a44ac03dd847ab16fa1d8d13ce60cc5",
              "d9a5e6e42e666f0f08867f51b343ce355f2f163ba15ef0cdd6a5cd7d37989dce"
            ]
          ]
        },
        s: {
          rendered: true,
          reason: "full",
          tiles: [
            [
              "cd884d9f42d455a5225e5ea3389047dd29453275ab3fd992c6ecc224b5ad192f"
            ],
            [
              "588b0778bb091eb9a53c99807dc90445849292ea772c893ad5a1fddfea8ad24f",
              "1cfec0bd7d2a86ef6d17da4e456a887ec58a7edd916634cc5cce038f4955dabf",
              "ae8131674c4a972f30e2e51f5d29891a5697193b1d369e4efd320ff5096645d0",
              "aeb8b9acb4dae0d98f2a51ba324b83587ca2272bf0895ec7b86057668e002740"
            ]
          ]
        },
        w: {
          rendered: true,
          reason: "full",
          tiles: [
            [
              "8a100a7e4f45be5ea8ce298fad2e1addd7bd7997a86bb054c833529352adc46c"
            ],
            [
              "6399bea6366e0c4f1283af6e4556c2f459953036c25348430f80b8395742f1c9",
              "32a7db01642f44b2fde88f08ec81a452f339ac3f7e87a42d4129901c5829c21a",
              "20165a1acd92a1f02086df5eb2d07d1633f4f6d6ccc496048ce3d621193e0227",
              "03dd0007cce8c6e2001b241fe127b8c71aae65f57ebafba2ba793e08331c4943"
            ]
          ]
        },
        u: {
          rendered: true,
          reason: "full",
          tiles: [
            [
              "8062cde41dd91e070c6feae9e5b75ef8cabd2d07455b755493f6edd056516c10"
            ],
            [
              "fde5b8f3fbfcec2c444ecc95943fccbbb7619edb20ca5571a8a8ea8f2344e658",
              "51fff9c6368fc6bda41a75a38c88301699d3dd53d66c983e929b2f248c15ed6b",
              "228a7d7ec1f45c0b5965c64e4acf93b3f3763bd3685f5ef418fc7d4e8835473d",
              "537f5e3247ac4f6c55b48c4683a9f29f01d9a6554643148753850cfb1a19f100"
            ]
          ]
        },
        d: {
          rendered: true,
          reason: "full",
          tiles: [
            [
              "97068ede0247f1067135af97f89022133b3d74f947feb8929a6bb2067b416b93"
            ],
            [
              "7710a7b660a63d843311f790cd73a4af36cc4a28235dd1c12b8b82f1133c63bf",
              "e939b45e521748d4aeb76e1c7bf63ffe4efd2ab5a0b3ae45bfa7b6f364b1945f",
              "6a318c9f726457c0d8c7aa50ffa78fa2b3c4395ee00ae52fc71d398d9843b97c",
              "2655c8c3daed54896e6375d04f83f9d002b32adaeac6162901ae91081290b6e8"
            ]
          ]
        }
      }
    }
  ],
  faces_rendered: 18,
  faces_reused: 0,
  ms: {
    open: 36,
    render: 14223,
    encode: 237
  }
};

// server/tests/contracts/render-jobs/manifest-tiles.json
var manifest_tiles_default = {
  schema: "truebex-tiles/1",
  job_id: "c3000000000000000000000000000002",
  project_id: "fd1f65c522298d6fbd318103c6601118",
  at_seq: 1,
  app_version: "1.0.0",
  quality: "standard",
  views: [
    {
      view: "ecaf16d70fa5862cbba8f2288b9fd593",
      title: "bedroom",
      eye_mm: [
        6750,
        2500,
        1600
      ],
      face_px: 512,
      tile_px: 256,
      levels: [
        256,
        512
      ],
      faces: {
        n: {
          rendered: false,
          reason: "carried",
          tiles: [
            [
              "849fba945c75643da309dc0c1ac42a24c35617ca91f4ee616d612d3fe50d1748"
            ],
            [
              "2daeb196e154035b0a165c0e76c6aa302c01cab6b1602d723e48fc83ec8b1394",
              "553f0c335b2c352bec85ad04d2b9b2c5750369b8f81b60e3fbf68da9002348b5",
              "c3d028c95a5c1391229f953e16d23565e034fe325f36c06eae22adbf33ebb41a",
              "ad0a1312e4a908d894d01ee5114b5de5b574e8196ad6b845833ded50a4a16786"
            ]
          ]
        },
        e: {
          rendered: false,
          reason: "carried",
          tiles: [
            [
              "6f2f466d689e56ed3cda6a1347700daf47ce02828770dd6b9af4020706d873eb"
            ],
            [
              "b8a366fcfbb45e9164e72c280dcb00f3b7341b98a39f20a5c144104a5dcf0f77",
              "96fbe5c09b1bffea66256c10eb64cf9e94d6f5822dae0000d7e2a05ae8dab89f",
              "d1cf7df00766fbbe402c9b0ab458d1c2fc427d59319aa527c5841050bb3573f7",
              "789139b909154df3c6e16a6a37841b43a5c80b4bc133722eed77ef01b00d97bb"
            ]
          ]
        },
        s: {
          rendered: false,
          reason: "carried",
          tiles: [
            [
              "bc46a146de2cf01fc915330882643a81bac351f4f4d4fc8f37f35f6471eabcd3"
            ],
            [
              "588dfb52d7d7f53a8b046fa4e65c48e814fa339a5ab024b3a41b0f5f59c7f9de",
              "aabb0c341fcfe957c7fa249c89c38f75dfab7345352c6087d6ac582062274189",
              "54d0f5a393d1e92fa0212aa0906d454fb993392ed4c1be03ef43bcd5e6d05715",
              "a565dfa53e6f30e7e04d87c134c5fff91dca297c23448625fe07dfbc8e9c0e8a"
            ]
          ]
        },
        w: {
          rendered: true,
          reason: "changed",
          tiles: [
            [
              "58ca325c550749cebb67700a6369754fc23ffdca20b4569ff260f696d788636d"
            ],
            [
              "ef0b02e84476b63c49fd65019044e366d9a26c40d19335b281e3955707a93846",
              "eaba667a9dafc2b85d8778a95e75190961690bd5fb866d7d61418f268e53edb0",
              "2bb6cf67ce0b04b75949856a6b11562a09c6bf6193f24fb894dd7c0c88b08945",
              "443446b71d5782a038d0f9e1c6ef680d5514bd5fbd7deca6ad58b289a42db3ee"
            ]
          ]
        },
        u: {
          rendered: false,
          reason: "carried",
          tiles: [
            [
              "5b3f598c29f3c6514b874460335354b6c959401e7bee02d7522a0ceeadd2c8f7"
            ],
            [
              "4cc130c81e032f53c908b98a98bc7d5fdf05ebf55fa11ebed8e971d054039b88",
              "ef27e12b6506a1a9a87042089dfd90c06f4b37e9d03cf746bb5d9d03980a509e",
              "2c2ad51f82085b5dd5dfdc6cb12df45c8779c0a3afde5a908d834c036e6b9e63",
              "7f5e77ae4427ec528344406828a6bd3c1c01b07ed3b631476f42bb505046059d"
            ]
          ]
        },
        d: {
          rendered: false,
          reason: "carried",
          tiles: [
            [
              "e0f5b5b89a8df7b5ca6b710d642d0627718639607e004ee8c60a2865333ab3f0"
            ],
            [
              "65f27d7190a4b2b74acfe6b532f589212ba607844d8c3f628d791b97a2385d23",
              "b7ce97a59b2dd78b25bbf2fa8dc318f457ba6836077f5cb726d437af42e39670",
              "d5216e1dbfcf6a817c4470c949faae4558dba8d4f6f830d736eb1e97c60ca840",
              "daa3022f0bb00d78cf60bbc089a3c79542eb25f74f90990b16c4cb1f102fea87"
            ]
          ]
        }
      }
    },
    {
      view: "8388104cbff98d2dba07fd23c19c83b5",
      title: "entry",
      eye_mm: [
        2250,
        1e3,
        1600
      ],
      face_px: 512,
      tile_px: 256,
      levels: [
        256,
        512
      ],
      faces: {
        n: {
          rendered: true,
          reason: "light",
          tiles: [
            [
              "f20073f57afa00bafa9cd2160c4d40091fb0abc55026eaef1c3bafd59a4daa76"
            ],
            [
              "a571e17770a9fba42e207bfa9ec4d37d554bc1cd191d13ef6ae15f3a093b7745",
              "387570e5643c0ae81fdaf4f4eb3a8d498bddeb84da62c0f7fc15d2581c93e5e2",
              "cd3cf35fdb8ede4b465c6f49e6cec798144a72df7d8708093b21a12beb9adcc4",
              "e5f4b794a1f3896ae207f1c26eacf81ef30612404578b5efde13b109dc61b8e4"
            ]
          ]
        },
        e: {
          rendered: true,
          reason: "light",
          tiles: [
            [
              "8cc70e172171e1d7f6c4caca1c988ea2125cc9539077e50e19fae133f7c16256"
            ],
            [
              "f7dd706a511cf81061f64900a9cff1934697870ce8ff0e06f9fbbbf0480aa04b",
              "e61f42694bedb645f60f246c1885a725198e76ea879d5257e9aeee647eea4762",
              "9851289f84df2275d1d8f1dc9458723832fc03140033f0fe2c5c62ac0e37a5ed",
              "9c1de0ac2b6355c9f6a0860d2c66dad71bc6a78cba93e5f8623b8846b5cd34eb"
            ]
          ]
        },
        s: {
          rendered: true,
          reason: "light",
          tiles: [
            [
              "d92164676b577bda0cc9ee5dfce501d5795b05cafcb5e33609d4c757bb05f8a4"
            ],
            [
              "b8b5023dd71cbd30e1accdca91788cf3d944803e553386339f48c8f9ac1c91a9",
              "4adc44cf2a45e8143bfc8a9a06359ef6b76e457d5021d22d5969bffd3fc11548",
              "8913bfee8fb0fbe6696ecfd60f15e2ae8114b35330cf9805a11d8b100a644c7e",
              "2f2aa3e4714c20e89881d69241938f93e421d3df675c5888c95cf6bf117a0a88"
            ]
          ]
        },
        w: {
          rendered: true,
          reason: "light",
          tiles: [
            [
              "9c2114ec101732285a04bb27c60f1c1baff65bf4704d8420424658cc51b1d23e"
            ],
            [
              "a829f7e21394eabc567f01c2a99abce07cb7633b279ed369e1af563900770e59",
              "b830c8f939f942a3568ed21eb71fa1689e4df5de882b122df7301d21c2392585",
              "7744738dd109d3ecbd405fceddfeab4c0fbdfd8a6dcfbf770b67dc9966783525",
              "44a921e8203f7ac8bcd1dff4ff053cb6953a29e808bbb3251db72c4aca3c6f56"
            ]
          ]
        },
        u: {
          rendered: true,
          reason: "light",
          tiles: [
            [
              "160afcf8319c5df5a062ecb5fb3cf32d0fce357356aa31d07b86106b8ec4db96"
            ],
            [
              "856a6ea9acf4568d32ca9cf81c3a5c9c75eac349f28282aeae6b7c1614e17816",
              "aa06544e628ad1748a196f8a2be13f51f0ee14e12250cee161c510ea39299fd6",
              "83a7e4ac7e57e3127607830dcd223320a2e9c39fe7ce7bdeb995fe5e79331efc",
              "418c627e4319a90c862f006937171d59545c39f6da8411e3444f77ef5e8e4ad6"
            ]
          ]
        },
        d: {
          rendered: true,
          reason: "light",
          tiles: [
            [
              "9fa50aa69053f5f27a245d1ee1d0783f310c467d0a7458d0f4d17bc621a8c6a9"
            ],
            [
              "0092af41cef8774b01ddca700aa9f570f8e9f843f7608349123d80d7d4aba7b3",
              "48cae77ef98ec83f50d583699462ed65e5bcffabede9931cd98dd5a7ed003f76",
              "3f838ef029ec9d43f888c9262a19a1ebac1a20a15d67fcc216e0b050c4144226",
              "5a30417d44540516a76a32fef53601d8d1d56518c5cab4c3ef0f8c9b7d215791"
            ]
          ]
        }
      }
    },
    {
      view: "aee49319c0d48a7a953f247b52c948be",
      title: "living",
      eye_mm: [
        2250,
        2500,
        1600
      ],
      face_px: 512,
      tile_px: 256,
      levels: [
        256,
        512
      ],
      faces: {
        n: {
          rendered: true,
          reason: "light",
          tiles: [
            [
              "4d6c5c0c94071e31fd151b45a93412310dd3607fbd7f03e26fb00b0e1fb6b74b"
            ],
            [
              "3762cac642ba9798805e00e2389af5244293793b61789ee46a0e2c5195a30335",
              "10bfe1d519d39fba2d7815d2228ed0de765361944962516c97f1e8c965b0dbd7",
              "6eea30513aa25c1cc67cf53962c72e43b6719a9975d888ca4d31b2400fa3d429",
              "e98273eb91f916e9d21742df4ee0c975f03e0fdeef8ea9f0a9343843dfbf12a2"
            ]
          ]
        },
        e: {
          rendered: true,
          reason: "light",
          tiles: [
            [
              "03d4ef03d1fab2099bb9ce7c28f80df30cad8fe875ad0555878064bc72c38364"
            ],
            [
              "5f61d180fba34428620367c64baa46c51062a1f31406dd8913c93ac40906b196",
              "e25be468fa813b0d0d40d797f01390230594bb7da5d3126515e0573908d8d973",
              "4f934ef535ddf64b7908b2baaf8f474bc83a05b390a536462d195b03b7d1e365",
              "5d50a7f15104dbce72d9cabdbcb0ad69f0f4d5133d61bb16b338e270e7704606"
            ]
          ]
        },
        s: {
          rendered: true,
          reason: "light",
          tiles: [
            [
              "f868c5fd5b8a47bbb221c1999f4107281bc9f8f9f675c108e4c9687ebec881a6"
            ],
            [
              "369e8eb10b39e97ec4574efdc3d2ecec5cdc46e6cc5e9b33b88aae9f4eb9a668",
              "892f9d2d09deaefcf5034f250f13e2990a6232b32ae8ba392154707e248e9e5a",
              "53e41fd50e2e65f962fabb4c0053ee2bc27e2c870364932f4fc127d50565d0f1",
              "1a8d20b8513d146a3a3ad2b35603c4b75c3652b00f92f2213e86b65c67864296"
            ]
          ]
        },
        w: {
          rendered: true,
          reason: "light",
          tiles: [
            [
              "352bcbe901e4d4187d9de2a25c5db908afa4d8ec5803b51482ed71d291f6eccc"
            ],
            [
              "8681c2b9775c73e4d93f404c20aba29d704b886188e7dd0aecdb7cbce7671532",
              "292d3300302df0b0bbb556f56d91c53cdbe2889bb609bd331b365fd41780a20a",
              "d0fa3edde6a6ce8491d8ac279aa488aa2833eda1109c1ec496b29f661a4b038c",
              "9765605f9c2f3393117c5c28c1f752e0357e11ee773c057f31d2b01e91886347"
            ]
          ]
        },
        u: {
          rendered: true,
          reason: "light",
          tiles: [
            [
              "cdb0d48b3b1c9996d5d0d3771dd3d3ebf0b76e9c4ab479551a3f193e54153455"
            ],
            [
              "317a173a225ff4cf86c05cf24e407fcfe106846121a039388b4d6ee22805dc5d",
              "1d0ea260d096d4b5fa4b9b58345c589c396347eddabcccab4e7c8dc4566aac8f",
              "0cf20116fef48e456bf3323d1b9b891b0a20536df080ea2159244cc81fefd974",
              "91acbc6c346188dca44803196c9583b281040a9943e803fc391907a921a8d896"
            ]
          ]
        },
        d: {
          rendered: true,
          reason: "light",
          tiles: [
            [
              "79cde5661db353c990de2741fd100221c5f6fdf58a49650ad47e3a62fc904e6d"
            ],
            [
              "368276ea8982a7c8d1587d7f061bb7618757c2c4b908c7159e276f49af65948c",
              "17351814c57a4637ce3fb643e7979a7f1f1ac48c9d4ad47a435457e7a83e536c",
              "82ae5c751a52f51366aacdecc0acdf5747803b923a9ad840493c15c9d049cfd9",
              "394a40fcba65bc5587802b3aa05cfd0e63d836c57c844120cdec18b961286263"
            ]
          ]
        }
      }
    }
  ],
  faces_rendered: 13,
  faces_reused: 5,
  ms: {
    open: 35,
    render: 10541,
    encode: 160
  }
};

// src/viewer/actions.ts
var HEX32 = /^[0-9a-f]{32}$/;
var COLOUR = /^#[0-9A-Fa-f]{6}$/;
var REF_KEYS = ["refs", "target", "host", "room", "replace"];
var MAX_MM = 1e6;
var NAME_MAX = 80;
var REF_KINDS = [
  "wall",
  "opening",
  "room",
  "slab",
  "object",
  "extrusion",
  "model",
  "sweep",
  "dim",
  "refplane",
  "line",
  "curve",
  "door",
  "window",
  "storey",
  "stair",
  "sheet",
  "layer"
];
var DIGEST_KINDS = { room: "room", wall: "wall", product: "object", opening: "opening" };
var REF = new RegExp(`^(${REF_KINDS.join("|")})#([0-9a-f]{32})$`);
var isHex32 = (value) => typeof value === "string" && HEX32.test(value);
var ref = (kind, id) => `${kind}#${id.toLowerCase()}`;
function refId(value) {
  if (typeof value !== "string") return null;
  const m = REF.exec(value.toLowerCase());
  return m ? m[2] : null;
}
var isRef = (value) => refId(value) !== null;
function hex32() {
  const bytes = new Uint8Array(16);
  globalThis.crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}
function rfc3339ms(at) {
  return at.toISOString();
}
function touchedOf(args) {
  const ids = /* @__PURE__ */ new Set();
  const record = args;
  for (const key of REF_KEYS) {
    const value = record[key];
    for (const v of Array.isArray(value) ? value : [value]) {
      const id = refId(v);
      if (id) ids.add(id);
    }
  }
  return [...ids].sort();
}
function fail(message) {
  throw new Error(`action: ${message}`);
}
var finiteMm = (v) => typeof v === "number" && Number.isFinite(v) && Math.abs(v) <= MAX_MM;
var isP3 = (v) => Array.isArray(v) && v.length === 3 && v.every(finiteMm);
function validateCall(call) {
  const refsOk = (refs) => Array.isArray(refs) && refs.length >= 1 && refs.length <= 100 && refs.every(isRef);
  switch (call.tool) {
    case "move": {
      const a = call.args;
      if (!refsOk(a.refs)) fail("move.refs: 1 to 100 refs <kind>#<id>");
      const given = ["by_mm", "to_mm", "along_mm", "rotate_deg"].filter((k) => a[k] !== void 0);
      if (given.length !== 1) fail("move: exactly one of by_mm, to_mm, along_mm, rotate_deg");
      if (a.by_mm !== void 0 && !isP3(a.by_mm)) fail("move.by_mm: three numbers (mm)");
      if (a.to_mm !== void 0 && (!isP3(a.to_mm) || a.refs.length !== 1)) fail("move.to_mm: one ref, three numbers");
      if (a.along_mm !== void 0 && !finiteMm(a.along_mm)) fail("move.along_mm: a number (mm)");
      if (a.rotate_deg !== void 0 && !(Math.abs(a.rotate_deg) <= 360)) fail("move.rotate_deg: -360 to 360");
      return;
    }
    case "fill": {
      const a = call.args;
      if (!isRef(a.target)) fail("fill.target: a ref <kind>#<id>");
      const f = a.finish;
      if (!f || !["paint", "wallpaper", "pattern3d", "none"].includes(f.kind)) fail("fill.finish.kind");
      if (f.colour !== void 0 && !COLOUR.test(f.colour)) fail("fill.finish.colour: #RRGGBB");
      if (f.roughness !== void 0 && !(f.roughness >= 0 && f.roughness <= 1)) fail("fill.finish.roughness: 0 to 1");
      if (f.texture !== void 0 && f.texture.length > 120) fail("fill.finish.texture: at most 120 characters");
      return;
    }
    case "apply_theme": {
      const a = call.args;
      if (!isRef(a.target)) fail("apply_theme.target: a ref <kind>#<id>");
      if (!a.theme || a.theme.length > 120) fail("apply_theme.theme: 1 to 120 characters");
      return;
    }
    case "place": {
      const a = call.args;
      if (a.kind !== "product") fail("place: only products travel in the log from a light client");
      const p = a.product;
      if (!p || !isHex32(p.supplier_id) || !p.sku || p.sku.length > 64 || !p.variant_id || p.variant_id.length > 64) {
        fail("place.product: supplier_id, sku, variant_id");
      }
      if (a.replace !== void 0 && !isRef(a.replace)) fail("place.replace: a ref <kind>#<id>");
      if (a.room !== void 0 && !isRef(a.room)) fail("place.room: a ref <kind>#<id>");
      if (a.room === void 0 && a.at_mm === void 0 && a.replace === void 0) fail("place: room, at_mm or replace");
      return;
    }
    default:
      fail("not a log-safe tool");
  }
}
function buildActionOp(input) {
  const author = input.author.toLowerCase();
  const replica = input.replicaId.toLowerCase();
  const session = input.session.toLowerCase();
  if (!isHex32(author)) fail("author: 32 hex (the person's author_id)");
  if (!isHex32(replica)) fail("replica_id: 32 hex");
  if (!isHex32(session)) fail("session: 32 hex");
  if (!Number.isInteger(input.baseSeq) || input.baseSeq < 0) fail("base_seq: 0 or more");
  validateCall(input.call);
  const opId = (input.opId ?? hex32()).toLowerCase();
  const requestId = (input.requestId ?? hex32()).toLowerCase();
  if (!isHex32(opId) || !isHex32(requestId)) fail("op_id, request_id: 32 hex");
  const at = typeof input.at === "string" ? input.at : rfc3339ms(input.at ?? /* @__PURE__ */ new Date());
  return {
    op_id: opId,
    author,
    author_kind: "person",
    at,
    replica_id: replica,
    base_seq: input.baseSeq,
    kind: "action",
    name: Array.from(input.name.trim()).slice(0, NAME_MAX).join(""),
    touched: touchedOf(input.call.args),
    action: { tool: input.call.tool, args: input.call.args, permission: "edit", session, request_id: requestId }
  };
}
function nudgeVector(bearingDeg, dir, stepMm) {
  const b = bearingDeg * Math.PI / 180;
  const forward = [Math.sin(b), Math.cos(b)];
  const right = [Math.cos(b), -Math.sin(b)];
  const [x, y] = dir === "forward" ? forward : dir === "back" ? [-forward[0], -forward[1]] : dir === "right" ? right : [-right[0], -right[1]];
  const mm = (v) => Math.round(v * stepMm) + 0;
  return [mm(x), mm(y), 0];
}
var moveBy = (refs, by) => ({ tool: "move", args: { refs, by_mm: by } });
var slideAlong = (ref2, along) => ({ tool: "move", args: { refs: [ref2], along_mm: along } });
var fillFace = (target, face, finish) => ({ tool: "fill", args: { target, face, finish } });
var applyTheme = (room, theme) => ({
  tool: "apply_theme",
  args: { theme, target: room, keep_products: true }
});
var swapProduct = (replace, product, room) => ({
  tool: "place",
  args: room ? { kind: "product", product, replace, room } : { kind: "product", product, replace }
});

// src/viewer/cachepolicy.ts
var TILE_BUDGET_BYTES = 150 * 1024 * 1024;
var APP_PAGES = ["/app/", "/app/project/"];
var TILE_PATH = /\/[0-9a-f]{64}\.jpg$/;
function isTileUrl(raw) {
  try {
    const url = new URL(raw);
    return (url.protocol === "https:" || url.protocol === "http:") && !url.search && TILE_PATH.test(url.pathname);
  } catch {
    return false;
  }
}
function pageKey(raw) {
  const url = new URL(raw);
  const path = url.pathname.endsWith("/") ? url.pathname : `${url.pathname}/`;
  return APP_PAGES.includes(path) ? `${url.origin}${path}` : null;
}
function requestRule(req) {
  if (req.method !== "GET" || req.authorized) return null;
  let url;
  try {
    url = new URL(req.url);
  } catch {
    return null;
  }
  if (isTileUrl(req.url)) return "tile";
  if (url.origin !== req.origin) return null;
  if (url.pathname.startsWith("/_next/static/")) return "static";
  if (req.mode === "navigate" && pageKey(req.url)) return "page";
  return null;
}
function planEviction(entries, budget, incoming = 0) {
  let total = incoming + entries.reduce((sum, e) => sum + Math.max(0, e.bytes), 0);
  if (total <= budget) return [];
  const order = [...entries].sort((a, b) => a.used - b.used || (a.url < b.url ? -1 : a.url > b.url ? 1 : 0));
  const out = [];
  for (const e of order) {
    if (total <= budget) break;
    out.push(e.url);
    total -= Math.max(0, e.bytes);
  }
  return out;
}

// src/viewer/outbox.ts
var MAX_BATCH = 200;
var KEEP_ACCEPTED = 20;
var PushError = class extends Error {
  constructor(retry, message, status = 0, code = "") {
    super(message);
    this.retry = retry;
    this.status = status;
    this.code = code;
  }
};
function applyResults(batch, answer) {
  const byId = new Map(answer.results.map((r) => [r.op_id, r]));
  return batch.map((entry) => {
    const r = byId.get(entry.op_id);
    if (!r || r.status === "not_processed") return entry;
    if (r.status === "accepted" || r.status === "duplicate") {
      return { ...entry, state: "accepted", seq: r.server_seq ?? void 0, reason: void 0 };
    }
    const w = r.winning?.[0];
    return {
      ...entry,
      state: "rejected",
      reason: r.reason ?? "conflict",
      winner: w ? { author: w.author, author_kind: w.author_kind, name: w.name, server_seq: w.server_seq } : null
    };
  });
}
function conflictLine(winner, me, names, text) {
  if (winner?.author_kind === "agent") return text.named(text.agent);
  if (winner && me && winner.author === me) return text.self;
  return text.named(winner && names.get(winner.author) || text.someone);
}
var flushing = null;
function flush(store, pid, push) {
  flushing ??= run(store, pid, push).finally(() => {
    flushing = null;
  });
  return flushing;
}
async function run(store, pid, push) {
  const out = { head: null, accepted: [], rejected: [], failed: [], waiting: 0, error: null };
  for (let round = 0; round < 1e3; round++) {
    const pending = (await store.list(pid)).filter((e) => e.state === "pending").sort((a, b) => a.created - b.created);
    if (!pending.length) break;
    const replica = pending[0].op.replica_id;
    const batch = pending.filter((e) => e.op.replica_id === replica).slice(0, MAX_BATCH);
    let answer;
    try {
      answer = await push(replica, batch.map((e) => e.op));
    } catch (err) {
      const error = err instanceof PushError ? err : new PushError(true, err instanceof Error ? err.message : String(err));
      if (error.retry) {
        out.error = error;
        out.waiting = pending.length;
        return out;
      }
      for (const e of batch) {
        const failed = { ...e, state: "failed", reason: error.message };
        await store.put(failed);
        out.failed.push(failed);
      }
      out.error = error;
      continue;
    }
    out.head = answer.head_seq;
    const updated = applyResults(batch, answer);
    let progressed = false;
    for (const e of updated) {
      if (e.state === "pending") continue;
      progressed = true;
      await store.put(e);
      (e.state === "accepted" ? out.accepted : out.rejected).push(e);
    }
    if (!progressed) {
      out.waiting = pending.length;
      break;
    }
  }
  await prune(store, pid);
  return out;
}
async function prune(store, pid) {
  const accepted = (await store.list(pid)).filter((e) => e.state === "accepted").sort((a, b) => b.created - a.created);
  for (const e of accepted.slice(KEEP_ACCEPTED)) await store.remove(e.op_id);
}
var MemoryOutbox = class {
  constructor() {
    this.rows = /* @__PURE__ */ new Map();
  }
  async list(pid) {
    return [...this.rows.values()].filter((e) => e.pid === pid).map((e) => ({ ...e }));
  }
  async put(entry) {
    this.rows.set(entry.op_id, { ...entry });
  }
  async remove(opId) {
    this.rows.delete(opId);
  }
};

// src/viewer/orientation.ts
var RAD = Math.PI / 180;
function lookFromOrientation(alphaDeg, betaDeg, gammaDeg) {
  const [a, b, g] = [alphaDeg * RAD, betaDeg * RAD, gammaDeg * RAD];
  const [ca, sa, cb, sb, cg, sg] = [Math.cos(a), Math.sin(a), Math.cos(b), Math.sin(b), Math.cos(g), Math.sin(g)];
  const x = -(ca * sg + sa * sb * cg);
  const y = -(sa * sg - ca * sb * cg);
  const z = -(cb * cg);
  const yaw = (Math.atan2(x, y) / RAD + 360) % 360;
  const pitch = Math.asin(Math.max(-1, Math.min(1, z))) / RAD;
  return { yawDeg: yaw, pitchDeg: pitch };
}
function angleDelta(a, b) {
  const d = ((a - b) % 360 + 540) % 360 - 180;
  return d === -180 ? 180 : d;
}
function bearingTo(from, to) {
  const [dx, dy, dz] = [to[0] - from[0], to[1] - from[1], (to[2] ?? 0) - (from[2] ?? 0)];
  const flat = Math.hypot(dx, dy);
  const yaw = (Math.atan2(dx, dy) / RAD + 360) % 360;
  const pitch = flat > 0 ? Math.atan2(dz, flat) / RAD - 8 : 0;
  return { yawDeg: yaw, pitchDeg: Math.max(-60, Math.min(60, pitch)) };
}

// src/viewer/tilediff.ts
var FACE_ORDER = ["n", "e", "s", "w", "u", "d"];
function diffTiles(prev, next) {
  const faces = [];
  const changed = [];
  const fetch = [];
  const seen = /* @__PURE__ */ new Set();
  for (const face of FACE_ORDER) {
    const after = next.faces[face]?.tiles ?? [];
    const before = prev?.faces[face]?.tiles ?? [];
    let any = false;
    after.forEach((level, l) => {
      level.forEach((sha, i) => {
        if (before[l]?.[i] === sha) return;
        any = true;
        changed.push(`${face}:${l}:${i}`);
        if (!seen.has(sha)) {
          seen.add(sha);
          fetch.push(sha);
        }
      });
    });
    if (any) faces.push(face);
  }
  return { faces, changed, fetch };
}
function levelFor(view, px) {
  const i = view.levels.findIndex((size) => size >= px);
  return i === -1 ? view.levels.length - 1 : i;
}
function levelAtMost(view, maxPx) {
  let best = 0;
  view.levels.forEach((size, i) => {
    if (size <= maxPx) best = i;
  });
  return best;
}
function tileUrls(view, tilesBase, level) {
  const base = tilesBase.replace(/\/$/, "");
  const out = [];
  for (const face of FACE_ORDER) for (const sha of view.faces[face]?.tiles?.[level] ?? []) out.push(`${base}/${sha}.jpg`);
  return [...new Set(out)];
}

// src/viewer/selftest.ts
var checks = 0;
var failures = [];
function check(name, ok, detail = "") {
  checks++;
  if (!ok) failures.push(`${name}${detail ? `: ${detail}` : ""}`);
}
var same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
var near = (a, b, eps = 1e-6) => Math.abs(a - b) <= eps;
var throws = (fn) => {
  try {
    fn();
    return false;
  } catch {
    return true;
  }
};
function builder() {
  const op = action_move_default;
  const wall = op.touched[0];
  const session = "5e55000000000000000000000000000a";
  const built = buildActionOp({
    author: op.author,
    replicaId: op.replica_id,
    baseSeq: op.base_seq,
    session,
    opId: op.op_id,
    at: op.at,
    name: op.name,
    call: moveBy([ref(DIGEST_KINDS.wall, wall)], [0, 600, 0])
  });
  check("builder.refs", same(built.action.args, { refs: [`wall#${wall}`], by_mm: [0, 600, 0] }), JSON.stringify(built.action.args));
  check("builder.touched", same(built.touched, [wall]) && same(built.touched, op.touched), JSON.stringify(built.touched));
  check("builder.tool", built.action.tool === op.action.tool);
  check("builder.args bytes", JSON.stringify(built.action.args) === JSON.stringify(op.action.args), JSON.stringify(op.action.args));
  check("builder.permission", built.action.permission === op.action.permission);
  const wire = built;
  const want = op;
  for (const key of Object.keys(wire).filter((k) => k !== "action")) {
    check(`builder.${key}`, same(wire[key], want[key]), `${JSON.stringify(wire[key])} != ${JSON.stringify(want[key])}`);
  }
  for (const key of Object.keys(want).filter((k) => !(k in wire))) {
    check(`builder omits ${key}`, key === "server_seq" && want[key] === 0, `the fixture has ${JSON.stringify(want[key])}`);
  }
  const { session: s1, request_id: r1, ...core } = built.action;
  check("builder.action core", same(core, op.action), JSON.stringify(core));
  check("builder session", s1 === session && /^[0-9a-f]{32}$/.test(r1) && !("session" in op.action));
  const base = { author: op.author, replicaId: op.replica_id, baseSeq: 3, session, name: "Edit" };
  check("bare id refused", throws(() => buildActionOp({ ...base, call: moveBy([wall], [0, 600, 0]) })));
  check("unknown kind refused", throws(() => buildActionOp({ ...base, call: moveBy([`sofa#${wall}`], [0, 600, 0]) })));
  check("bare target refused", throws(() => buildActionOp({ ...base, call: fillFace(wall, "left", { kind: "paint", colour: "#C8B79E" }) })));
  check("ref parse", refId(`WALL#${wall.toUpperCase()}`) === wall && refId(wall) === null && refId("wall#nope") === null);
  check("digest kinds", ref(DIGEST_KINDS.product, wall) === `object#${wall}` && ref(DIGEST_KINDS.opening, wall) === `opening#${wall}`);
  const [a, b] = ["0199c6a2e00070028000000000000001", "0199c6a2e00070068000000000000002"];
  const [room, sofa] = [ref(DIGEST_KINDS.room, a), ref(DIGEST_KINDS.product, b)];
  const product = { supplier_id: "f8afe1ba2b0bf97f23ef888f040cf46a", sku: "TABLE-FJORD-CT", variant_id: "default" };
  check("touched swap", same(touchedOf(swapProduct(sofa, product, room).args), [a, b]));
  check("touched dedupe", same(touchedOf({ refs: [sofa, room.toUpperCase(), sofa] }), [a, b]));
  check("touched ignores names and bare ids", same(touchedOf({ theme: "nordic-calm", target: room, refs: [b] }), [a]));
  const swap = buildActionOp({ ...base, name: "Swap coffee table", call: swapProduct(sofa, product, room) });
  check("swap tool", swap.action.tool === "place" && same(swap.action.args, { kind: "product", product, replace: sofa, room }));
  check("swap touched", same(swap.touched, [a, b]) && swap.base_seq === 3 && swap.kind === "action");
  const fill = buildActionOp({ ...base, call: fillFace(room, "floor", { kind: "paint", colour: "#C8B79E" }) });
  check("fill args", same(fill.action.args, { target: room, face: "floor", finish: { kind: "paint", colour: "#C8B79E" } }));
  check("theme args", same(applyTheme(room, "nordic-calm").args, { theme: "nordic-calm", target: room, keep_products: true }));
  check("ids minted", /^[0-9a-f]{32}$/.test(fill.op_id) && fill.op_id !== swap.op_id && /^[0-9a-f]{32}$/.test(fill.action.request_id));
  check("at is RFC 3339 ms", /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$/.test(fill.at));
  check("name capped at 80", buildActionOp({ ...base, name: "x".repeat(200), call: slideAlong(ref(DIGEST_KINDS.opening, a), 50) }).name.length === 80);
  check("move needs exactly one", throws(() => buildActionOp({ ...base, call: { tool: "move", args: { refs: [room], by_mm: [1, 0, 0], along_mm: 5 } } })));
  check("bad colour refused", throws(() => buildActionOp({ ...base, call: fillFace(room, "floor", { kind: "paint", colour: "beige" }) })));
  check("bad author refused", throws(() => buildActionOp({ ...base, author: "me", call: moveBy([room], [0, 0, 0]) })));
  check("negative base refused", throws(() => buildActionOp({ ...base, baseSeq: -1, call: moveBy([room], [0, 0, 0]) })));
  check("place object refused", throws(() => buildActionOp({ ...base, call: { tool: "place", args: { kind: "object" } } })));
  check("nudge north-left", same(nudgeVector(0, "left", 250), [-250, 0, 0]));
  check("nudge east-left", same(nudgeVector(90, "left", 250), [0, 250, 0]));
  check("nudge south-forward", same(nudgeVector(180, "forward", 50), [0, -50, 0]));
  check("nudge west-back", same(nudgeVector(270, "back", 50), [50, 0, 0]));
  check("nudge no -0", !Object.is(nudgeVector(0, "forward", 50)[0], -0));
}
function finishBuilder() {
  const op = action_finish_default;
  const wall = op.touched[0];
  const session = "5e55000000000000000000000000000b";
  const built = buildActionOp({
    author: op.author,
    replicaId: op.replica_id,
    baseSeq: op.base_seq,
    session,
    opId: op.op_id,
    at: op.at,
    name: op.name,
    call: fillFace(ref(DIGEST_KINDS.wall, wall), "left", { kind: "paint", colour: "#C0392B" })
  });
  check("fill.tool", built.action.tool === op.action.tool, built.action.tool);
  check("fill.args bytes", JSON.stringify(built.action.args) === JSON.stringify(op.action.args), JSON.stringify(built.action.args));
  check("fill.permission", built.action.permission === op.action.permission);
  check("fill.touched", same(built.touched, [wall]) && same(built.touched, op.touched), JSON.stringify(built.touched));
  const wire = built;
  const want = op;
  for (const key of Object.keys(wire).filter((k) => k !== "action")) {
    check(`fill.${key}`, same(wire[key], want[key]), `${JSON.stringify(wire[key])} != ${JSON.stringify(want[key])}`);
  }
  for (const key of Object.keys(want).filter((k) => !(k in wire))) {
    check(`fill omits ${key}`, key === "server_seq" && want[key] === 0, `the fixture has ${JSON.stringify(want[key])}`);
  }
  const { session: s1, request_id: r1, ...core } = built.action;
  check("fill.action core", same(core, op.action), JSON.stringify(core));
  check("fill session", s1 === session && /^[0-9a-f]{32}$/.test(r1) && !("session" in op.action));
}
function tileDiff() {
  const views = (m) => m.views;
  const fulls = new Map(views(manifest_panorama_default).map((v) => [v.view, v]));
  check("diff views", views(manifest_tiles_default).length === 3 && views(manifest_tiles_default).every((v) => fulls.has(v.view)));
  let faces = 0;
  for (const update of views(manifest_tiles_default)) {
    const full2 = fulls.get(update.view);
    const d = diffTiles(full2, update);
    const rendered = FACE_ORDER.filter((f) => update.faces[f].rendered);
    faces += rendered.length;
    check(`diff faces ${update.view}`, same(d.faces, rendered), `${JSON.stringify(d.faces)} != ${JSON.stringify(rendered)}`);
    const want = rendered.reduce((n, f) => n + update.faces[f].tiles.flat().length, 0);
    check(`diff tiles ${update.view}`, d.changed.length === want && d.fetch.length <= want, `${d.changed.length} of ${want}`);
    check(`diff same ${update.view}`, diffTiles(update, update).changed.length === 0);
  }
  check("diff rendered faces", faces === manifest_tiles_default.faces_rendered, `${faces} != ${manifest_tiles_default.faces_rendered}`);
  const full = views(manifest_panorama_default)[0];
  check("diff first", same(diffTiles(null, full).faces, ["n", "e", "s", "w", "u", "d"]));
  check("levels 256 and 512", same(full.levels, [256, 512]) && full.tile_px === 256, JSON.stringify(full.levels));
  check("level for 600 px", levelFor(full, 600) === 1 && levelFor(full, 300) === 1 && levelFor(full, 200) === 0 && levelFor(full, 5e3) === 1);
  check("level at most 2048", levelAtMost(full, 2048) === 1 && levelAtMost(full, 300) === 0);
  const urls = tileUrls(full, "https://tiles.example.com/tiles/", 0);
  check("tile urls", urls.length === 6 && urls.every((u) => isTileUrl(u) && u.startsWith("https://tiles.example.com/tiles/")));
}
function cachePolicy() {
  const origin = "https://truebex.com";
  const sha = "28746b924afdd6a1eb06011a2811b57ac05f67e96c27779cd9d6ed348f462846";
  const rule = (url, extra = {}) => requestRule({ url, method: "GET", mode: "no-cors", origin, ...extra });
  check("budget 150 MB", TILE_BUDGET_BYTES === 150 * 1024 * 1024);
  check("tile on the CDN", rule(`https://tiles.truebex.com/tiles/${sha}.jpg`) === "tile");
  check("tile on the API", rule(`https://api.truebex.com/tiles/${sha}.jpg`) === "tile");
  check("tile with a query is not one", rule(`https://api.truebex.com/tiles/${sha}.jpg?x=1`) === null);
  check("build files", rule(`${origin}/_next/static/chunks/app.js`) === "static");
  check("app page", rule(`${origin}/app/project/?id=abc`, { mode: "navigate" }) === "page");
  check("page key drops the query", pageKey(`${origin}/app/project/?id=abc`) === `${origin}/app/project/`);
  check("other pages untouched", rule(`${origin}/dashboard/`, { mode: "navigate" }) === null && rule(`${origin}/`, { mode: "navigate" }) === null);
  for (const path of ["/projects", "/projects/abc/ops?after=1", "/auth/me", "/jobs/abc", "/market/prices", "/uploads", "/licence/account"]) {
    check(`API ${path} never cached`, rule(`https://api.truebex.com${path}`) === null && rule(`${origin}${path}`) === null);
  }
  check("POST never cached", rule(`https://api.truebex.com/tiles/${sha}.jpg`, { method: "POST" }) === null);
  check("credentials never cached", rule(`${origin}/_next/static/a.js`, { authorized: true }) === null);
  const entries = [
    { url: "a", bytes: 60, used: 3 },
    { url: "b", bytes: 60, used: 1 },
    { url: "c", bytes: 60, used: 2 }
  ];
  check("fits", planEviction(entries, 180).length === 0);
  check("LRU out", same(planEviction(entries, 150), ["b"]));
  check("LRU with incoming", same(planEviction(entries, 150, 60), ["b", "c"]));
  check("ties by url", same(planEviction([{ url: "y", bytes: 10, used: 1 }, { url: "x", bytes: 10, used: 1 }], 10), ["x"]));
}
async function outbox() {
  const op = action_move_default;
  const store = new MemoryOutbox();
  const pid = "0199c6a2f1007a3c8b5e2d4f6a7b8c9d";
  const make = (n, id) => {
    const built = buildActionOp({
      author: op.author,
      replicaId: op.replica_id,
      baseSeq: 12,
      session: "5e55000000000000000000000000000a",
      name: `Edit ${n}`,
      call: moveBy([ref(DIGEST_KINDS.product, id)], [0, 50, 0])
    });
    return { op_id: built.op_id, pid, op: built, state: "pending", label: `Edit ${n}`, created: n };
  };
  const refs = ["0199c6a2e00070068000000000000001", "0199c6a2e00070068000000000000002", "0199c6a2e00070068000000000000003"];
  const entries = refs.map((r, i) => make(i + 1, r));
  for (const e of entries) await store.put(e);
  let out = await flush(store, pid, async () => {
    throw new PushError(true, "offline");
  });
  check("offline waits", out.waiting === 3 && (await store.list(pid)).every((e) => e.state === "pending"));
  const sent = [];
  let seq = 12;
  out = await flush(store, pid, async (_replica, ops) => {
    sent.push(ops.map((o) => o.op_id));
    const results = [];
    let stopped = false;
    for (const o of ops) {
      if (stopped) results.push({ op_id: o.op_id, status: "not_processed" });
      else if (o.op_id === entries[1].op_id) {
        stopped = true;
        results.push({
          op_id: o.op_id,
          status: "rejected",
          reason: "conflict",
          winning: [{ op_id: "f".repeat(32), server_seq: 13, author: "0199c6a2f0007000a000000000000007", author_kind: "person", name: "Move sofa" }]
        });
      } else results.push({ op_id: o.op_id, status: "accepted", server_seq: ++seq });
    }
    return { head_seq: seq, results };
  });
  const after = new Map((await store.list(pid)).map((e) => [e.op_id, e]));
  check("first accepted", after.get(entries[0].op_id)?.state === "accepted" && after.get(entries[0].op_id)?.seq === 13);
  check("second rejected with its winner", after.get(entries[1].op_id)?.state === "rejected" && after.get(entries[1].op_id)?.winner?.name === "Move sofa");
  check("the winner keeps its author_kind", after.get(entries[1].op_id)?.winner?.author_kind === "person");
  check("third sent again", sent.length === 2 && same(sent[1], [entries[2].op_id]) && after.get(entries[2].op_id)?.state === "accepted");
  check("rejected never re-sent", !sent[1].includes(entries[1].op_id) && out.rejected.length === 1 && out.accepted.length === 2);
  const bad = make(9, refs[0]);
  await store.put(bad);
  out = await flush(store, pid, async () => {
    throw new PushError(false, "ops[0].touched: sorted and unique", 422, "validation_failed");
  });
  check("422 fails", out.failed.length === 1 && (await store.list(pid)).find((e) => e.op_id === bad.op_id)?.state === "failed");
}
function authors() {
  const text = {
    named: (name) => `${name} changed this first \u2014 your edit was replaced`,
    self: "You changed this first on another device \u2014 your edit was replaced",
    agent: "An assistant or script",
    someone: "Someone"
  };
  const me = "0199c6a2f0007000a000000000000042";
  const sam = "0199c6a2f0007000a000000000000007";
  const key = "0199c6a2f0007000a0000000000000aa";
  const stranger = "0199c6a2f0007000a0000000000000bb";
  const names = /* @__PURE__ */ new Map([[sam, "Sam"]]);
  const won = (author, author_kind) => ({ author, author_kind, name: "Move sofa", server_seq: 13 });
  check("authors: self", conflictLine(won(me, "person"), me, names, text) === text.self);
  check("authors: a member by name", conflictLine(won(sam, "person"), me, names, text) === "Sam changed this first \u2014 your edit was replaced");
  check("authors: an API key reads as an agent", conflictLine(won(key, "agent"), me, names, text) === "An assistant or script changed this first \u2014 your edit was replaced");
  check("authors: an agent whatever its id", conflictLine(won(sam, "agent"), me, names, text) === "An assistant or script changed this first \u2014 your edit was replaced");
  check("authors: an unknown person", conflictLine(won(stranger, "person"), me, names, text) === "Someone changed this first \u2014 your edit was replaced");
  check("authors: no winner", conflictLine(null, me, names, text) === "Someone changed this first \u2014 your edit was replaced");
  check("authors: stored before author_kind", conflictLine(won(sam), me, names, text) === "Sam changed this first \u2014 your edit was replaced");
  check("authors: signed out", conflictLine(won(me, "person"), null, names, text) === "Someone changed this first \u2014 your edit was replaced");
}
function orientation() {
  const upright = lookFromOrientation(0, 90, 0);
  check("upright faces north", near(upright.yawDeg, 0) && near(upright.pitchDeg, 0), JSON.stringify(upright));
  const west = lookFromOrientation(90, 90, 0);
  check("alpha 90 faces west", near(west.yawDeg, 270), JSON.stringify(west));
  check("flat looks down", near(lookFromOrientation(0, 0, 0).pitchDeg, -90));
  const tilted = lookFromOrientation(0, 120, 0);
  check("tilted back looks up", near(tilted.pitchDeg, 30, 1e-6), JSON.stringify(tilted));
  const landscape = lookFromOrientation(0, 0, -90);
  check("landscape is level", near(landscape.pitchDeg, 0, 1e-6), JSON.stringify(landscape));
  check("angle delta", angleDelta(10, 350) === 20 && angleDelta(350, 10) === -20 && angleDelta(180, 0) === 180);
  const toKitchen = bearingTo([4200, 1800, 1600], [8600, 2400, 1600]);
  check("hotspot bearing", Math.round(toKitchen.yawDeg) === 82 && toKitchen.pitchDeg < 0, JSON.stringify(toKitchen));
}
async function main() {
  builder();
  finishBuilder();
  tileDiff();
  cachePolicy();
  await outbox();
  authors();
  orientation();
  if (failures.length) {
    console.error(`selftest: ${failures.length} of ${checks} checks failed`);
    for (const f of failures) console.error(`  FAIL ${f}`);
    process.exitCode = 1;
  } else {
    console.log(`selftest: ${checks} checks passed (action builder, the app's fill, tile diff, cache policy, outbox, authors, orientation)`);
  }
}
main().catch((err) => {
  console.error("selftest crashed:", err);
  process.exitCode = 1;
});
