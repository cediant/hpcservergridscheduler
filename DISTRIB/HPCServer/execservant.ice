
module HPCServer{

	sequence<string> StringList;

	dictionary<string,string> HPCJob;
	dictionary<string,HPCJob> HPCJobDict;
	
	
	interface ExecServant {
		["ami","amd"] idempotent string gExec(string inputstring);
	};

};
