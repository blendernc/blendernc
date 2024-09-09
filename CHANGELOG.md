# Changelog

<!--next-version-placeholder-->

## v0.7.0 (2024-09-09)

### Feature

* Fix cmap for versions of blender > 3.0, and fix the requirements for blender4 and python >3.10 ([`ac58aee`](https://github.com/blendernc/blendernc/commit/ac58aeefb90973f79a50d3cd1c4a76a27c69079f))
* Fix colorramp for blender > 3.3 ([`6de5bb9`](https://github.com/blendernc/blendernc/commit/6de5bb9ba9ca2c187047287a9cd38f20f0d142e9))
* Implement xarray load check ([`2d9a495`](https://github.com/blendernc/blendernc/commit/2d9a4953ca34833cbe2dcecf1f26ce92a02f8c6a))
* Ensure xarray load ([`b5d31c3`](https://github.com/blendernc/blendernc/commit/b5d31c368acabafc0bc329969acebb4453c1f7e8))
* Add support to include python path in preferences and better indication when xarray is not properly installed ([`7565685`](https://github.com/blendernc/blendernc/commit/756568586f0c78885275754fb89165b46480dfa0))

### Fix

* Blendernc version for semantic-release ([`e0da126`](https://github.com/blendernc/blendernc/commit/e0da126fc9b665f82c2b7d5163fe16e1a47ceef0))
* Change release number in blendernc package ([`e9483dd`](https://github.com/blendernc/blendernc/commit/e9483ddfad23c367dbf7ba855ddbb01659830b05))
* Change release number in blendernc package ([`cc35066`](https://github.com/blendernc/blendernc/commit/cc3506610c8bb5cba096ab27db81ea1b585ccd99))
* Crash when creating basic nodes ([`685a177`](https://github.com/blendernc/blendernc/commit/685a1774cae1ea07faefea18f15caee7dd15a9eb))
* Crash when creating basic nodes ([`0516af8`](https://github.com/blendernc/blendernc/commit/0516af884fdf15ec49f3454d32333553b501d89e))
* Fix vulnerabilities 08-2023 ([`4b95e62`](https://github.com/blendernc/blendernc/commit/4b95e62648bc8cdf6ccf3536076a7dca1c7379a4))
* Adding python path only if the addon has been loaded ([`17d0d49`](https://github.com/blendernc/blendernc/commit/17d0d49eb3ffd538fffd1c30f386ad05f1a929cf))
* Fix messages to have custom error messsages ([`eaf9dea`](https://github.com/blendernc/blendernc/commit/eaf9dea032305679e2a24dbdc9ed1be59338e4ff))

## v0.6.0 (2022-07-12)
### Feature
* Fix time axis selection and fix label for node tests ([`4c909c5`](https://github.com/blendernc/blendernc/commit/4c909c59732af617f9b077788b09610fa3e5076d))
* Add preference, fix date selection of cftime ([`3a82746`](https://github.com/blendernc/blendernc/commit/3a82746b8b4fde50a13a3a339e125200d3c65ee5))
* Allow nodes to be automatically load by only updating one node, smaller issues have been solved, particularly with the implementation of time selection and grid import ([`1681959`](https://github.com/blendernc/blendernc/commit/16819596597c1a5a97bb43df645e7ad5c3de5e91))

### Fix
* Fix backwards compatibility with blender 2.83 and blendernc preferece ([`618b54c`](https://github.com/blendernc/blendernc/commit/618b54c1d1adbd63b6e55ef108ed291a500f1b86))
* Update precommit black rev ([`36ff67f`](https://github.com/blendernc/blendernc/commit/36ff67fb3351fabfe4dd7f2ac02598ca0afc5d28))
* Remove bottleneck dependencies to remove issue of installation ([`99032ca`](https://github.com/blendernc/blendernc/commit/99032ca6b5772312b9179b8c9e00468a225632da))
* Add support for coordname including time for preference frame computation ([`a6ae7aa`](https://github.com/blendernc/blendernc/commit/a6ae7aab625ef460d10b811c4725921630cac48f))
* Solve security vulnerabilities in dependencies (Pillow) ([`d19fa33`](https://github.com/blendernc/blendernc/commit/d19fa33016381ecf704d56043508c1bc7f9bf479))
* Fix test and using multiple outputs for one single math node ([`11b58d2`](https://github.com/blendernc/blendernc/commit/11b58d2acab371d4bdc6a3e15ee4bbcbf2700334))
* Solve bugs and add support of multiple outputs ([`a4a3124`](https://github.com/blendernc/blendernc/commit/a4a31246a4e1039d8157ff376889ea540fe5a9d3))
* Add full suport of frame selection & fix other bugs ([`d91000e`](https://github.com/blendernc/blendernc/commit/d91000e3db0e61083545e2dc03832b43c5754d77))

## v0.5.1 (2022-03-30)
### Fix
* Add colorcet to installation instructions ([`c3e43f1`](https://github.com/blendernc/blendernc/commit/c3e43f1bbf99b07c509c5e74c0ce588b1e91c9ba))

## v0.5.0 (2022-02-25)
### Feature
* Add colorcet colormaps support ([`6bd8d83`](https://github.com/blendernc/blendernc/commit/6bd8d839a6709ba7ffad5a3cd35b6c0d7a764c7b))

### Fix
* Version of ecmwflibs ([`d98e9db`](https://github.com/blendernc/blendernc/commit/d98e9dbec3efbfd987f8bb9b99eb655d21a6c0a3))

## v0.4.11 (2021-09-20)


## v0.4.10 (2021-09-03)
### Fix
* Bump manual version of bl_info, blender greps the bl_info instead of running the script ([`0e02620`](https://github.com/blendernc/blendernc/commit/0e0262087d844200750ff865664ae764ec7cf4ad))
* Distribution and change __init__.py using version pattern ([`a530014`](https://github.com/blendernc/blendernc/commit/a530014cdc603194fedc2da024953f9ee1fc17e4))

### Documentation
* Dev install of commitlint ([`03c959c`](https://github.com/blendernc/blendernc/commit/03c959cdf35a54049b6e50f8a4125766b4f55e85))
* Add commitlint installation ([`26244e7`](https://github.com/blendernc/blendernc/commit/26244e79b70c918627ebd8cf4577a573d136752d))
* Add info to contribute ([`c1a0e6d`](https://github.com/blendernc/blendernc/commit/c1a0e6da184d75fba054220beab0709a01497974))

## v0.4.9 (2021-09-02)
### Fix
* Add placeholder for changelog update ([`0ef525f`](https://github.com/blendernc/blendernc/commit/0ef525fa2b2acbd48d11ec49855608ad5c83278f))

