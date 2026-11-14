/* The Navi callouts row (Gameplay tab, HOS_OPT_NAVI_CALLOUTS: 1 On, the game's; 0 Off). Players of the remake asked for a quieter
   Navi (Ship of Harkinian's option to turn her interruptions off is the one most cited).

   The remake's Navi calls out ("Hey! Listen!", her sign on the screen) when an area hint is waiting: the maps and the logic
   graphs place NaviAreaHintEventActor where a place has a hint (its AreaHintEventName and AreaHintPriority), whose AI node
   ExecuteNaviAreaHintRegist (f_80cceec0) registers it with Navi's hint manager (f_80ccf0f0). Asking Navi then plays the
   hint's event (Sequence/NaviHintEvent: SeqQueryIsNaviAreaHint, SeqQueryGetNaviAreaHintName). With the row Off,
   nx2/oot_patches.py patch_navi_hints has the registration return as the game's own does with its registry full: no area
   hint, nothing to call out, none to give. Story dialogue (events), Z-targeting and her lock-on hints about enemies
   (OneShotNaviHintBeforehandLoadEventRequestRegister, NaviLockOnHint) are other paths and stay; so do her balloon chats
   (TriggerNaviRequestBallonMessage). A hint registered before the row went Off stays until its place is left. */
#include "hos.h"
#include "../gpu/vk/vk_api.h"

int rx_option(int id, int otherwise);

int hos_oot_navi_hints_off(void) { return rx_option(HOS_OPT_NAVI_CALLOUTS, 1) == 0; }
